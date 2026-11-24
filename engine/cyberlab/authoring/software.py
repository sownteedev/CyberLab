from contextlib import contextmanager
from dataclasses import replace
import json
import logging
import os
from pathlib import Path
import sqlite3
from threading import Event, Lock, RLock, Thread, Timer
from uuid import uuid4

import yaml

from cyberlab.lab import list_labs
from cyberlab.lab.models import NodeSoftware
from cyberlab.lab.loader import _LabYamlLoader
from cyberlab.lab.package import load_snapshot
from cyberlab.lab.software import STARTUP_TIMEOUT_SECONDS, catalog, enabled, fingerprint
from cyberlab.runtime import RuntimeFailure

ACTIVE = {"QUEUED", "PREPARING", "CANCELLING"}

class SoftwarePreparation:
    def __init__(self, database, authoring, runtime, active_images=None):
        self.database = Path(database)
        self.authoring = authoring
        self.runtime = runtime
        self.active_images = active_images or (lambda: ())
        self.lock = RLock()
        self.workers = {}
        self.automatic = {}
        self.image_leases = {}
        self.build_lock = Lock()
        self.closing = False
        with self.connection() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS software_environments (image TEXT PRIMARY KEY, spec TEXT NOT NULL, base TEXT NOT NULL, receipt TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS software_jobs (id TEXT PRIMARY KEY, owner INTEGER NOT NULL, data TEXT NOT NULL);
            ''')
            for identifier, data in connection.execute("SELECT id,data FROM software_jobs").fetchall():
                job = json.loads(data)
                if job['state'] in ACTIVE:
                    job.update(state="FAILED", error="Daemon restarted; preparation interrupted. Retry safely.")
                    connection.execute("UPDATE software_jobs SET data=? WHERE id=?", (json.dumps(job), identifier))
        self.database.chmod(0o600)

    @contextmanager
    def connection(self):
        with self.lock:
            connection = sqlite3.connect(self.database, timeout=10)
            try:
                with connection:
                    yield connection
            finally:
                connection.close()

    def node(self, identifier, revision, node_id, uid):
        snapshot = self.authoring.store.get(identifier, uid, revision)
        lab = load_snapshot(snapshot)
        self.authoring.policy.validate(lab)
        node = next((node for node in lab.nodes if node.id == node_id), None)
        if node is None or not enabled(node.software):
            raise ValueError("Select software for this Ubuntu machine first")
        return snapshot, node

    @contextmanager
    def image_lease(self, cancel):
        with self.lock:
            lease = self.image_leases.setdefault(cancel, {"depth": 0, "images": set()})
            lease["depth"] += 1
        try:
            yield
        finally:
            with self.lock:
                lease["depth"] -= 1
                if not lease["depth"]:
                    self.image_leases.pop(cancel, None)

    def _pin_image(self, cancel, image):
        with self.lock:
            if cancel in self.image_leases:
                self.image_leases[cancel]["images"].add(image)

    def resolve(self, software, cancel=None):
        with self.connection() as connection:
            record = connection.execute("SELECT receipt FROM software_environments WHERE image=?", (software.environment,)).fetchone()
            if record is None:
                raise RuntimeFailure("Software environment is not prepared on this computer; prepare it before publishing or starting")
            image = self.runtime.verify(software, json.loads(record[0]))
            self._pin_image(cancel, image)
            return image

    def plan(self, identifier, revision, node_id, uid):
        _, node = self.node(identifier, revision, node_id, uid)
        ready = False
        if node.software.environment:
            try:
                self.resolve(node.software)
                ready = True
            except Exception:
                pass
        return {"id": identifier, "revision": revision, "node": node_id, "ready": ready,
                "spec": fingerprint(node.software), "catalog": catalog(),
                "software": {"gui": node.software.gui, "apps": list(node.software.apps), "packages": list(node.software.packages)},
                "latest_job": self.latest(identifier, node_id, uid)}

    def latest(self, identifier, node_id, uid):
        with self.connection() as connection:
            records = connection.execute("SELECT data FROM software_jobs WHERE owner=? ORDER BY rowid DESC", (uid,)).fetchall()
            for data, in records:
                job = json.loads(data)
                if job['draft'] == identifier and job['node'] == node_id:
                    return self._job_status(job)
            return None

    def get(self, identifier, uid):
        with self.connection() as connection:
            record = connection.execute("SELECT data FROM software_jobs WHERE id=? AND owner=?", (identifier, uid)).fetchone()
            if record is None:
                raise ValueError("Software preparation job not found")
            return self._job_status(json.loads(record[0]))

    def _job_status(self, job):
        if job['state'] in ACTIVE and job['id'] not in self.workers:
            return {**job, "state": "FAILED", "message": "",
                    "error": "Software preparation interrupted; retry when storage is available"}
        return job

    def write(self, job):
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO software_jobs VALUES (?,?,?)", (job['id'], job['owner'], json.dumps(job)))

    def prepare(self, identifier, revision, node_id, uid):
        _, node = self.node(identifier, revision, node_id, uid)
        base = self.runtime.base()
        with self.lock:
            if self.closing:
                raise RuntimeFailure("Daemon is shutting down")
            if uid in self.automatic:
                raise RuntimeFailure("Wait for or cancel your current software preparation")
            for job_id in self.workers:
                job = self.get(job_id, self.workers[job_id][2])
                if job['owner'] == uid:
                    if (job['draft'], job['revision'], job['node']) == (identifier, revision, node_id):
                        return job
                    raise RuntimeFailure("Wait for or cancel your current software preparation")
            if len(self.workers) + len(self.automatic) >= 2:
                raise RuntimeFailure("Software preparation capacity reached; retry later")
            with self.connection() as connection:
                connection.execute("DELETE FROM software_jobs WHERE id IN (SELECT id FROM software_jobs WHERE owner=? ORDER BY rowid DESC LIMIT -1 OFFSET 48)", (uid,))
            job = {"id": uuid4().hex, "owner": uid, "draft": identifier, "revision": revision, "node": node_id,
                   "spec": fingerprint(node.software), "state": "QUEUED", "progress": 0, "message": "Queued", "error": "", "environment": ""}
            cancel = Event()
            worker = Thread(target=self.run, args=(job, node.software, base, cancel), daemon=True)
            self.write(job)
            self.workers[job['id']] = (cancel, worker, uid)
            worker.start()
            return dict(job)

    def cached_or_prepare(self, software, base, cancel, progress):
        try:
            self.cleanup_unreferenced()
        except Exception:
            logging.warning('Software image cleanup skipped; existing images retained', exc_info=True)
        while not self.build_lock.acquire(timeout=.1):
            if cancel.is_set():
                raise RuntimeFailure("Preparation cancelled")
        try:
            if cancel.is_set():
                raise RuntimeFailure("Preparation cancelled")
            with self.connection() as connection:
                records = connection.execute("SELECT receipt FROM software_environments WHERE spec=? AND base=? ORDER BY rowid DESC", (fingerprint(software), base)).fetchall()
            for data, in records:
                candidate = json.loads(data)
                try:
                    self.runtime.verify(replace(software, environment=candidate['image']), candidate)
                    self._pin_image(cancel, candidate['image'])
                    return candidate
                except Exception:
                    continue
            receipt = self.runtime.prepare(software, base, cancel, progress)
            if cancel.is_set():
                raise RuntimeFailure("Preparation cancelled")
            with self.connection() as connection:
                connection.execute("INSERT OR REPLACE INTO software_environments VALUES (?,?,?,?)", (receipt['image'], fingerprint(software), base, json.dumps(receipt)))
                self._pin_image(cancel, receipt['image'])
            return receipt
        finally:
            self.build_lock.release()

    def prepare_lab(self, lab, uid, cancel, skip_nodes=()):
        with self.image_lease(cancel):
            return self._prepare_lab(lab, uid, cancel, skip_nodes)

    def _prepare_lab(self, lab, uid, cancel, skip_nodes):
        if not any(enabled(node.software) and node.id not in skip_nodes for node in lab.nodes):
            return lab
        done = Event()
        with self.lock:
            if self.closing:
                raise RuntimeFailure("Daemon is shutting down")
            if uid in self.automatic or any(owner == uid for _, _, owner in self.workers.values()):
                raise RuntimeFailure("Wait for or cancel your current software preparation")
            if len(self.workers) + len(self.automatic) >= 2:
                raise RuntimeFailure("Software preparation capacity reached; retry later")
            self.automatic[uid] = (cancel, done)
        timeout = Timer(STARTUP_TIMEOUT_SECONDS, cancel.set)
        timeout.daemon = True
        timeout.start()
        try:
            nodes = []
            for node in lab.nodes:
                if cancel.is_set():
                    raise RuntimeFailure("Preparation cancelled")
                software = node.software
                if enabled(software) and node.id not in skip_nodes:
                    try:
                        image = self.resolve(software, cancel)
                    except RuntimeFailure:
                        receipt = self.cached_or_prepare(software, self.runtime.base(), cancel, lambda *args: None)
                        image = self.resolve(replace(software, environment=receipt['image']))
                    node = replace(node, software=replace(software, environment=image))
                nodes.append(node)
            return replace(lab, nodes=tuple(nodes))
        finally:
            timeout.cancel()
            with self.lock:
                self.automatic.pop(uid, None)
                done.set()

    def run(self, job, software, base, cancel):
        with self.image_lease(cancel):
            self._run(job, software, base, cancel)

    def _run(self, job, software, base, cancel):
        def progress(message, percent):
            if cancel.is_set():
                raise RuntimeFailure("Preparation cancelled")
            job.update(state="PREPARING", message=message, progress=percent)
            self.write(job)
        try:
            receipt = self.cached_or_prepare(software, base, cancel, progress)
            with self.lock:
                if cancel.is_set():
                    raise RuntimeFailure("Preparation cancelled")
                job['environment'] = receipt['image']
            self.authoring.store.get(job['draft'], job['owner'], job['revision'])
            job.update(state="READY", progress=100, message="Environment ready; apply it to the reviewed draft revision")
        except Exception as error:
            job.update(state="CANCELLED" if cancel.is_set() else "FAILED", error=str(error)[:4096])
        finally:
            with self.lock:
                try:
                    self.write(job)
                finally:
                    self.workers.pop(job['id'], None)

    def cancel(self, identifier, uid):
        with self.lock:
            job = self.get(identifier, uid)
            if identifier in self.workers:
                self.workers[identifier][0].set()
                job.update(state="CANCELLING", message="Cancelling preparation")
                self.write(job)
            return job

    def apply(self, identifier, uid):
        from .service import summary
        job = self.get(identifier, uid)
        if job['state'] != 'READY':
            raise ValueError("Software environment is not ready")
        with self.authoring.store.lock:
            snapshot, node = self.node(job['draft'], job['revision'], job['node'], uid)
            if fingerprint(node.software) != job['spec']:
                raise ValueError("Machine software changed; prepare the current revision")
            self.resolve(replace(node.software, environment=job['environment']))
            document = yaml.safe_load(snapshot['definition'])
            next(item for item in document['nodes'] if item['id'] == job['node'])['software']['environment'] = job['environment']
            return summary(self.authoring.store.change(job['draft'], uid, job['revision'], definition=json.dumps(document, ensure_ascii=False, indent=2)))

    def require_ready(self, lab):
        for node in lab.nodes:
            if enabled(node.software):
                self.resolve(node.software)

    def shutdown(self):
        with self.lock:
            self.closing = True
            workers = list(self.workers.values())
            automatic = list(self.automatic.values())
            for cancel, _, _ in workers:
                cancel.set()
            for cancel, _ in automatic:
                cancel.set()
        for _, worker, _ in workers:
            worker.join(timeout=45)
        for _, done in automatic:
            done.wait(timeout=45)

    def referenced_images(self):
        protected = set()
        specifications = set()
        try:
            protected.update(self.active_images())
        except Exception:
            raise RuntimeFailure("Cannot verify active software environments") from None
        drafts = self.authoring.store.list(0, include_definition=True)
        revisions = {entry['id']: (entry['owner'], entry['revision']) for entry in drafts}
        for entry in drafts:
            try:
                definition = yaml.load(entry['definition'], Loader=_LabYamlLoader)
                if not isinstance(definition, dict) or not isinstance(definition.get('nodes', []), list):
                    raise ValueError
                for node in definition.get('nodes', ()):
                    software = node.get('software') or {}
                    environment = software.get('environment', '')
                    if environment:
                        protected.add(environment)
                    selected = NodeSoftware(software.get('gui', False), tuple(software.get('apps', ())),
                                            tuple(software.get('packages', ())))
                    if enabled(selected):
                        specifications.add(fingerprint(selected))
            except (yaml.YAMLError, AttributeError, TypeError, ValueError, RecursionError):
                raise RuntimeFailure("Cannot verify saved software environments") from None
        try:
            for lab in list_labs(self.authoring.catalog):
                protected.update(node.software.environment for node in lab.nodes if node.software.environment)
                specifications.update(fingerprint(node.software) for node in lab.nodes if enabled(node.software))
        except Exception:
            raise RuntimeFailure("Cannot verify catalog software environments") from None
        with self.connection() as connection:
            for lease in self.image_leases.values():
                protected.update(lease['images'])
            if specifications:
                base = self.runtime.base()
                protected.update(image for image, spec in connection.execute(
                    "SELECT image,spec FROM software_environments WHERE base=?", (base,)) if spec in specifications)
            for row in connection.execute("SELECT data FROM software_jobs"):
                try:
                    job = json.loads(row[0])
                    environment = job.get("environment", "")
                except (TypeError, ValueError):
                    raise RuntimeFailure("Cannot verify software preparation jobs") from None
                applicable = job.get('state') == 'READY' and revisions.get(job.get('draft')) == (job.get('owner'), job.get('revision'))
                if environment and (job.get('state') in ACTIVE or applicable):
                    protected.add(environment)
        return {image for image in protected if isinstance(image, str) and image.startswith("sha256:")}

    def cleanup_unreferenced(self):
        cleanup = getattr(self.runtime, "cleanup_images", None)
        if cleanup is None:
            return set()
        with self.authoring.lifecycle_lock:
            if not self.build_lock.acquire(blocking=False):
                return set()
            try:
                with self.authoring.store.lock, self.lock:
                    protected = self.referenced_images()
                    removed = set(cleanup(protected))
                    if removed:
                        with self.connection() as connection:
                            connection.executemany("DELETE FROM software_environments WHERE image=?", ((image,) for image in removed))
                    return removed
            finally:
                self.build_lock.release()
