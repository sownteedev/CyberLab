from pathlib import Path
from dataclasses import replace
from hashlib import sha256
import json
from threading import RLock
from time import monotonic
from uuid import uuid4

from cyberlab.lab import get_lab, list_labs
from cyberlab.lab.catalog import LabInUseError, LabCatalogError, package_digest, read_package, remove_lab
from cyberlab.lab.package import digest as snapshot_digest, load_snapshot
from cyberlab.lab.networking import overlapping_subnets
from cyberlab.policy import RuntimePolicy
from cyberlab.runtime import Runtime, RuntimeFailure
from cyberlab.session import Session, SessionState, timestamp
from cyberlab.session.persistence import PracticeLimit
from cyberlab.session.reports import ReportLimit
from cyberlab.session.quiz import QuizLimit
from cyberlab.session.submissions import PreparedSubmission, checkpoint_archives, workspace_hashes
from cyberlab.terminal import Terminals, TerminalNotFound
from cyberlab.imports import ImportRecord, MAX_SESSION_BYTES, MAX_SESSION_IMPORTS, import_path, validate_import
from cyberlab.lab.environment import workspace
from cyberlab import workspace as workspace_data
from cyberlab.assessment import evaluate, public_report, submission_archive
from cyberlab.parameters import resolve_parameters
from cyberlab.quiz import QuizRevisionChanged, evaluate_quiz, pre_start_answers, public_questions, requires_pre_start, session_report

class DocumentationNotFound(Exception):
    """This Lab has no packaged documentation."""


class SessionNotFound(Exception):
    """The requested Session does not exist or is not visible to this caller."""


class SessionLimit(Exception):
    """A bounded MVP Session quota has been reached."""

class CheckReportNotFound(Exception):
    """The requested Checkwork report is not visible to this caller."""


class SessionBusy(Exception):
    """A Session is capturing evidence; retry its mutation afterward."""

class Engine:
    def __init__(self, catalog: Path, policy: RuntimePolicy, runtime: Runtime, practice_store=None):
        self.catalog = catalog
        self.policy = policy
        self.runtime = runtime
        self.practice_store = practice_store
        self._sessions = {}
        self._session_packages = {}
        self._imports = {}
        self._network_reservations = {}
        self._checking = set()
        self._prepared_submissions = {}
        self._lock = RLock()
        self._terminals = Terminals(runtime)
        if self.practice_store is not None:
            self.practice_store.discard_unsaved_quizzes()
            for session, package in self.practice_store.load_sessions():
                self._sessions[session.id] = session
                if package is not None:
                    self._session_packages[session.id] = package

    def labs(self):
        return list_labs(self.catalog)

    def lab_digest(self, lab_id):
        return package_digest(self.catalog, lab_id)

    def lab(self, lab_id):
        return get_lab(self.catalog, lab_id)

    def documentation(self, identifier, uid, session=False):
        with self._lock:
            lab = self._visible(identifier, uid).lab if session else self.lab(identifier)
            if lab.documentation is None or lab.documentation.content is None:
                raise DocumentationNotFound("Lab has no packaged documentation")
            return {"lab_id": lab.metadata.id, "version": lab.metadata.version,
                    "title": lab.metadata.name, "format": "markdown", "content": lab.documentation.content}

    def checkwork(self, session_id, uid):
        return self._capture_report(session_id, uid)

    def prepare_submission(self, session_id, uid):
        return self._capture_report(session_id, uid, submission=True)

    def _capture_report(self, session_id, uid, *, submission=False):
        with self._lock:
            session = self._mutable(session_id, uid)
            if session.state != SessionState.RUNNING:
                raise RuntimeFailure("Checkwork requires a running Session")
            if not submission and not session.lab.settings.checkwork:
                raise RuntimeFailure("Checkwork is not enabled in this Lab")
            if self.practice_store is None:
                raise RuntimeFailure("Checkwork report storage is unavailable")
            package = self._session_packages.get(session.id)
            if package is None:
                raise RuntimeFailure("Captured Lab package is unavailable")
            quiz = self.practice_store.get_quiz_attempt(session.id, session.owner_uid)
            self._checking.add(session.id)
        try:
            started_at = timestamp()
            deadline = monotonic() + 120
            referenced = {item.node for item in session.lab.assessment.results + session.lab.assessment.artifacts}
            workspaces, errors = {}, {}
            for node in session.lab.nodes:
                if not submission and node.id not in referenced:
                    continue
                if monotonic() >= deadline:
                    errors[node.id] = "Checkwork capture timed out"
                    continue
                try:
                    workspaces[node.id] = self.runtime.workspace(session, node)
                except RuntimeFailure as error:
                    errors[node.id] = str(error)
            if monotonic() > deadline:
                raise RuntimeFailure("Checkwork capture exceeded its deadline; no report was saved")
            if submission and errors:
                raise RuntimeFailure("Submission requires a complete workspace capture; Session was not stopped")
            report = evaluate(session, workspaces, errors, snapshot_digest(package["definition"], package["assets"]),
                              assess=session.lab.settings.checkwork)
            if quiz is not None:
                report["quiz"] = quiz
            report_id = uuid4().hex
            report["id"] = report_id
            report["capture_started_at"] = started_at
            report["created_at"] = timestamp()
            if submission:
                if not report["submission_ready"]:
                    raise RuntimeFailure("Required submission evidence is missing or invalid; Session was not stopped")
                report["purpose"] = "submission"
                submission_archive(report)
                archives = checkpoint_archives(session, workspaces)
            with self._lock:
                if self._sessions.get(session.id) is not session:
                    raise RuntimeFailure("Session changed during Checkwork; no report was saved")
                try:
                    if submission:
                        now = report["created_at"]
                        self.practice_store.save_checkpoint(
                            session.id, session.owner_uid, session.created_at, now, now, "SAVED",
                            package["definition"], archives, package, parameters=dict(session.parameters),
                            check_report=report)
                        session = replace(session, checkpoint_at=now, updated_at=now)
                        self._sessions[session.id] = session
                        self._prepared_submissions[session.id] = PreparedSubmission(
                            report_id, session, workspace_hashes(archives), quiz)
                    else:
                        self.practice_store.save_check_report(
                            report_id, session.id, session.owner_uid, report["created_at"],
                            json.dumps(report, ensure_ascii=True, separators=(",", ":")))
                except (ReportLimit, PracticeLimit) as error:
                    raise SessionLimit(str(error)) from None
            return public_report(report)
        finally:
            with self._lock:
                self._checking.discard(session.id)

    def finalize_submission(self, session_id, report_id, uid):
        with self._lock:
            session = self._mutable(session_id, uid)
            prepared = self._prepared_submissions.get(session_id)
            if prepared is None or prepared.report_id != report_id or prepared.session is not session:
                raise RuntimeFailure("Submission is stale; prepare and export the current Session again")
            self.check_report(report_id, uid)
            if prepared.cleanup_started:
                stopped = self.stop(session_id, uid)
                self._prepared_submissions[session_id] = replace(prepared, session=stopped)
                return stopped
            if session.state != SessionState.RUNNING:
                raise RuntimeFailure("Finalizing a submission requires its original running Session")
            if self.practice_store.get_quiz_attempt(session.id, session.owner_uid) != prepared.quiz:
                raise RuntimeFailure("Quiz changed after submission capture; prepare and export again")
            self._checking.add(session_id)
        try:
            deadline = monotonic() + 120
            workspaces = {}
            for node in session.lab.nodes:
                if monotonic() >= deadline:
                    raise RuntimeFailure("Submission verification timed out; Session was not stopped")
                workspaces[node.id] = self.runtime.workspace(session, node)
            if monotonic() > deadline:
                raise RuntimeFailure("Submission verification timed out; Session was not stopped")
            if workspace_hashes(checkpoint_archives(session, workspaces)) != prepared.workspaces:
                raise RuntimeFailure("Workspace changed after submission capture; prepare and export again")
            with self._lock:
                if self._sessions.get(session_id) is not session:
                    raise RuntimeFailure("Session changed during submission verification; inspect its state")
                self._checking.discard(session_id)
                stopped = self.stop(session_id, uid)
                self._prepared_submissions[session_id] = replace(prepared, session=stopped, cleanup_started=True)
                return stopped
        finally:
            with self._lock:
                self._checking.discard(session_id)

    def check_reports(self, uid, session_id=None):
        with self._lock:
            if self.practice_store is None:
                return []
            return self.practice_store.list_check_reports(uid, session_id=session_id)

    def check_report(self, report_id, uid):
        with self._lock:
            if self.practice_store is None:
                raise CheckReportNotFound("Checkwork report storage is unavailable")
            report = self.practice_store.get_check_report(report_id, uid)
            if report is None:
                raise CheckReportNotFound("Checkwork report not found")
            return public_report(report)

    def delete_check_report(self, report_id, uid):
        with self._lock:
            if self.practice_store is None:
                raise CheckReportNotFound("Checkwork report storage is unavailable")
            if not self.practice_store.delete_check_report(report_id, uid):
                raise CheckReportNotFound("Checkwork report not found")
            return True

    def export_submission(self, report_id, uid):
        with self._lock:
            if self.practice_store is None:
                raise CheckReportNotFound("Checkwork report storage is unavailable")
            report = self.practice_store.get_check_report(report_id, uid)
            if report is None:
                raise CheckReportNotFound("Checkwork report not found")
            return submission_archive(report)

    def submit_quiz(self, session_id, answers, uid):
        with self._lock:
            session = self._mutable(session_id, uid)
            if self.practice_store is None:
                raise RuntimeFailure("Quiz result storage is unavailable")
            report = session_report(session, answers, timestamp())
            try:
                self.practice_store.save_quiz_attempt(
                    session.id, session.owner_uid, report["created_at"],
                    json.dumps(report, ensure_ascii=True, separators=(",", ":")))
            except QuizLimit as error:
                raise SessionLimit(str(error)) from None
            return report

    def quiz_attempt(self, session_id, uid):
        with self._lock:
            self._visible(session_id, uid)
            if self.practice_store is None:
                return None
            return self.practice_store.get_quiz_attempt(session_id, uid)

    def _lab_quiz_snapshot(self, lab_id):
        if self.practice_store is None:
            raise RuntimeFailure("Lab quiz result storage is unavailable")
        definition, assets, digest = read_package(self.catalog, lab_id)
        lab = load_snapshot({"definition": definition, "assets": dict(assets)})
        if lab.metadata.id != lab_id:
            raise LabCatalogError("Lab identity changed while capturing its quiz")
        return lab, digest

    def lab_quiz(self, lab_id, uid):
        with self._lock:
            lab, digest = self._lab_quiz_snapshot(lab_id)
            return {"lab_id": lab_id, "lab_name": lab.metadata.name, "lab_version": lab.metadata.version,
                    "lab_digest": digest, "questions": public_questions(lab.quiz),
                    "pre_start_required": requires_pre_start(lab.quiz),
                    "attempt": self.practice_store.lab_quizzes.get(lab_id, uid, digest)}

    def submit_lab_quiz(self, lab_id, digest, answers, uid):
        with self._lock:
            lab, current_digest = self._lab_quiz_snapshot(lab_id)
            if digest != current_digest:
                raise QuizRevisionChanged("Lab revision changed; reopen the quiz before submitting")
            report = {"format": "cyberlab-lab-quiz/v1", "lab_id": lab_id,
                      "lab_version": lab.metadata.version, "lab_digest": digest,
                      **evaluate_quiz(lab.quiz, answers), "created_at": timestamp()}
            try:
                self.practice_store.lab_quizzes.save(lab_id, uid, digest, report)
            except QuizLimit as error:
                raise SessionLimit(str(error)) from None
            return report

    def delete_lab_quiz(self, lab_id, uid):
        with self._lock:
            self._lab_quiz_snapshot(lab_id)
            return self.practice_store.lab_quizzes.delete(lab_id, uid)

    def imports(self, session_id, uid):
        with self._lock:
            self._visible(session_id, uid)
            return tuple(self._imports.get(session_id, {}).values())

    def import_file(self, session_id, node_id, name, data, uid):
        with self._lock:
            self._mutable(session_id, uid)
            session = self.status(session_id, uid)
            if session.state != SessionState.RUNNING:
                raise RuntimeFailure("Import requires a running Session")
            node = next((node for node in session.lab.nodes if node.id == node_id), None)
            if node is None:
                raise TerminalNotFound("Node not found")
            validate_import(name, data)
            records = self._imports.setdefault(session.id, {})
            if len(records) >= MAX_SESSION_IMPORTS or sum(record.size for record in records.values()) + len(data) > MAX_SESSION_BYTES:
                raise SessionLimit("Import quota reached; reset the Session to clear temporary files")
            identifier = uuid4().hex
            record = ImportRecord(identifier, node_id, name, import_path(node, identifier, name), len(data), sha256(data).hexdigest())
            records[identifier] = record
            try:
                self.runtime.import_file(session, record, data)
                record = replace(record, state="COMPLETE")
            except Exception as error:
                message = str(error) if isinstance(error, RuntimeFailure) else "Unexpected import failure; inspect imports before retrying"
                record = replace(record, state="FAILED", error=message)
            records[identifier] = record
            return record

    def _workspace_node(self, session_id, node_id, uid):
        session = self.status(session_id, uid)
        if session.state != SessionState.RUNNING:
            raise RuntimeFailure("Workspace access requires a running Session")
        node = next((node for node in session.lab.nodes if node.id == node_id), None)
        if node is None:
            raise TerminalNotFound("Node not found")
        return session, node

    def list_workspace(self, session_id, node_id, uid):
        with self._lock:
            session, node = self._workspace_node(session_id, node_id, uid)
            entries = self.runtime.workspace(session, node)
            return {"session_id": session.id, "node": node.id, "root": workspace(node), "source": "live",
                    "entries": [entry.metadata() for entry in sorted(entries, key=lambda entry: entry.path)]}

    def export_workspace(self, session_id, node_id, path, uid, file=False):
        with self._lock:
            session, node = self._workspace_node(session_id, node_id, uid)
            workspace_data.relative_path(path, root=not file)
            entries = self.runtime.workspace(session, node)
            if file:
                return workspace_data.file_contents(entries, path)
            return workspace_data.make_archive(workspace_data.select(entries, path))

    def import_workspace(self, session_id, node_id, name, data, uid):
        with self._lock:
            self._mutable(session_id, uid)
            session, node = self._workspace_node(session_id, node_id, uid)
            workspace_data.folder_name(name)
            if len(data) > workspace_data.MAX_UPLOAD_ARCHIVE:
                raise ValueError("Folder archive exceeds its transfer limit")
            entries = workspace_data.read_archive(data, limit=workspace_data.MAX_UPLOAD_CONTENT)
            size = sum(entry.size for entry in entries)
            records = self._imports.setdefault(session.id, {})
            if len(records) >= MAX_SESSION_IMPORTS or sum(record.size for record in records.values()) + size > MAX_SESSION_BYTES:
                raise SessionLimit("Import quota reached; reset the Session to clear temporary files")
            identifier = uuid4().hex
            record = ImportRecord(identifier, node.id, name, f"{workspace(node)}/{name}", size,
                                  sha256(data).hexdigest(), kind="directory")
            records[identifier] = record
            try:
                self.runtime.import_workspace(session, node, name, entries)
                record = replace(record, state="COMPLETE")
            except Exception as error:
                message = str(error) if isinstance(error, RuntimeFailure) else "Folder import failed; inspect workspace before retrying"
                record = replace(record, state="FAILED", error=message)
            records[identifier] = record
            return record

    def _visible(self, session_id, uid):
        session = self._sessions.get(session_id)
        if session is None or (uid != 0 and uid != session.owner_uid):
            raise SessionNotFound("Session not found")
        return session

    def _mutable(self, session_id, uid):
        session = self._visible(session_id, uid)
        if session_id in self._checking:
            raise SessionBusy("Checkwork is capturing this Session; retry after it completes")
        return session

    def _quota(self, uid, exclude=None):
        active = [
            session for session in self._sessions.values()
            if session.id != exclude and session.state not in (SessionState.STOPPED, SessionState.SUSPENDED)
        ]
        if len(active) >= self.policy.max_active_sessions:
            raise SessionLimit("Global active Session limit reached")
        if sum(session.owner_uid == uid for session in active) >= self.policy.max_sessions_per_user:
            raise SessionLimit("User active Session limit reached")

    def _set(self, session, state, error=""):
        updated = session.transition(state, error)
        self._sessions[session.id] = updated
        if state == SessionState.FAILED:
            self._terminals.close_session(session.id)
        return updated

    def _start(self, session, workspaces=None):
        try:
            if any(identifier != session.id and overlapping_subnets(session.lab, lab)
                   for identifier, lab in self._network_reservations.items()):
                raise RuntimeFailure("Static subnet overlaps another Session; stop that Session or use a different subnet")
            self._network_reservations[session.id] = session.lab
            if workspaces is not None:
                self.runtime.start(session, workspaces=workspaces)
            else:
                self.runtime.start(session)
        except Exception as error:
            message = str(error) if isinstance(error, RuntimeFailure) else "Unexpected runtime start failure"
            try:
                self.runtime.remove(session.id)
                self._network_reservations.pop(session.id, None)
            except Exception:
                message += "; cleanup incomplete, retry stop"
            return self._set(session, SessionState.FAILED, message)
        return self._set(session, SessionState.RUNNING)

    def _reserve_history(self):
        required = len(self._sessions) - self.policy.max_session_history + 1
        if required <= 0:
            return
        stopped = sorted(
            (session for session in self._sessions.values() if session.state == SessionState.STOPPED and not getattr(session, "checkpoint_at", "")),
            key=lambda session: (session.updated_at, session.created_at, session.id),
        )
        if len(stopped) < required:
            raise SessionLimit("Session history is full; stop an unused Session or discard an old checkpoint")
        for session in stopped[:required]:
            self._sessions.pop(session.id)
            self._prepared_submissions.pop(session.id, None)
            self._session_packages.pop(session.id, None)
            self._imports.pop(session.id, None)
            self._network_reservations.pop(session.id, None)

            if self.practice_store is not None:
                self.practice_store.delete_quiz_attempt(session.id, session.owner_uid)

    def start(self, lab_id, uid, parameters=None):
        with self._lock:
            package = None
            preparation = None
            if self.practice_store is not None:
                definition, assets, digest = read_package(self.catalog, lab_id)
                package = {"definition": definition, "assets": dict(assets)}
                lab = load_snapshot(package)
                if lab.metadata.id != lab_id:
                    raise LabCatalogError("Lab identity changed while capturing its package")
                preparation = self.practice_store.lab_quizzes.get(lab_id, uid, digest)
            else:
                lab = self.lab(lab_id)
            prepared_answers = pre_start_answers(lab.quiz, preparation)
            session_id = uuid4().hex
            if any(not parameter.public and parameter.id in (parameters or {}) for parameter in lab.parameters):
                raise ValueError("Internal parameters cannot be overridden at Session start")
            lab, resolved_parameters = resolve_parameters(lab, parameters, session_id)
            self.policy.validate(lab)
            self._quota(uid)
            self._reserve_history()
            now = timestamp()
            session = Session(session_id, lab, uid, SessionState.PREPARING, now, now,
                              parameters=tuple((key, str(value)) for key, value in sorted(resolved_parameters.items())))
            if prepared_answers is not None:
                report = session_report(session, prepared_answers, preparation["created_at"])
                report.update(source="pre-start", lab_digest=digest)
                try:
                    self.practice_store.save_quiz_attempt(
                        session.id, uid, report["created_at"], json.dumps(report, ensure_ascii=True))
                except QuizLimit as error:
                    raise SessionLimit(str(error)) from None
            self._sessions[session.id] = session
            if package is not None:
                self._session_packages[session.id] = package
            return self._start(session)

    def check_runtime(self, lab, uid):
        with self._lock:
            session_id = uuid4().hex
            lab, _values = resolve_parameters(lab, None, session_id)
            self.policy.validate(lab)
            self._quota(uid)
            self._reserve_history()
            now = timestamp()
            session = Session(session_id, lab, uid, SessionState.PREPARING, now, now)
            self._sessions[session.id] = session
            issue = ""
            try:
                session = self._start(session)
                if session.state != SessionState.RUNNING:
                    issue = session.error
                else:
                    for node in lab.nodes:
                        self.runtime.workspace(session, node)
            except Exception as error:
                issue = str(error) if isinstance(error, RuntimeFailure) else "Runtime readiness check failed"
            finally:
                stopped = self.stop(session.id, uid)
            if stopped.state != SessionState.STOPPED:
                issue = (issue + "; " if issue else "") + stopped.error
            else:
                self._sessions.pop(session.id, None)
            ready = not issue
            return {"ready": ready, "runtime_verified": ready and self.runtime.name == "docker",
                    "runtime": self.runtime.name, "checked_at": timestamp(),
                    "cleanup_complete": stopped.state == SessionState.STOPPED,
                    "cleanup_session_id": "" if stopped.state == SessionState.STOPPED else stopped.id,
                    "issues": [] if ready else [{"stage": "runtime", "path": "/nodes", "message": issue}]}

    def check_lab_update(self, lab_id, uid):
        with self._lock:
            self.lab(lab_id)
            if any(session.lab.metadata.id == lab_id and session.state != SessionState.STOPPED for session in self._sessions.values()):
                raise LabInUseError("Lab has active Sessions; stop them before updating")

    def status(self, session_id, uid):
        with self._lock:
            session = self._visible(session_id, uid)
            if session.state == SessionState.RUNNING:
                try:
                    if not self.runtime.running(session):
                        session = self._set(session, SessionState.FAILED, "One or more nodes stopped")
                except RuntimeFailure as error:
                    session = self._set(session, SessionState.FAILED, str(error))
            return session

    def sessions(self, uid):
        with self._lock:
            return tuple(
                self.status(session.id, uid) for session in tuple(self._sessions.values())
                if uid == 0 or session.owner_uid == uid
            )

    def stop(self, session_id, uid):
        with self._lock:
            session = self._mutable(session_id, uid)
            if session.state == SessionState.STOPPED:
                return session
            session = self._set(session, SessionState.STOPPING)
            self._terminals.close_session(session.id)
            try:
                self.runtime.remove(session.id)
            except Exception as error:
                message = str(error) if isinstance(error, RuntimeFailure) else "Unexpected runtime cleanup failure"
                return self._set(session, SessionState.FAILED, message)
            self._imports.pop(session.id, None)
            self._network_reservations.pop(session.id, None)
            return self._set(session, SessionState.STOPPED)

    def reset(self, session_id, uid):
        with self._lock:
            session = self._mutable(session_id, uid)
            if session.checkpoint_at and session.id not in self._session_packages:
                raise RuntimeFailure(session.error or "Captured Lab package is unavailable")
            self.policy.validate(session.lab)
            self._quota(session.owner_uid, exclude=session_id)
            session = self._set(session, SessionState.RESETTING)
            self._terminals.close_session(session.id)
            try:
                self.runtime.remove(session.id)
            except Exception as error:
                message = str(error) if isinstance(error, RuntimeFailure) else "Unexpected runtime cleanup failure"
                return self._set(session, SessionState.FAILED, message)
            self._imports.pop(session.id, None)
            if self.practice_store is not None:
                self.practice_store.delete_checkpoint(session.id)
                self.practice_store.delete_quiz_attempt(session.id, session.owner_uid)
            session = replace(session, checkpoint_at="")
            return self._start(session)

    def _save_checkpoint(self, session, state):
        if self.practice_store is None:
            raise RuntimeFailure("Practice checkpoint storage is unavailable")
        package = self._session_packages.get(session.id)
        if package is None:
            raise RuntimeFailure("Captured Lab package is unavailable; checkpoint was not saved")
        workspaces = {}
        for node in session.lab.nodes:
            entries = self.runtime.workspace(session, node)
            node_uid = node.user.uid if node.user else 65534
            node_gid = node.user.gid if node.user else 65534
            workspaces[node.id] = workspace_data.make_archive(entries, uid=node_uid, gid=node_gid)
        now = timestamp()
        try:
            self.practice_store.save_checkpoint(session.id, session.owner_uid, session.created_at, now, now,
                                                state, package["definition"], workspaces, package,
                                                parameters=dict(session.parameters))
        except PracticeLimit as error:
            raise SessionLimit(str(error)) from None
        session = replace(session, checkpoint_at=now, updated_at=now)
        self._sessions[session.id] = session
        return session

    def save(self, session_id, uid):
        with self._lock:
            self._mutable(session_id, uid)
            session = self.status(session_id, uid)
            if session.state != SessionState.RUNNING:
                raise RuntimeFailure("Saving a checkpoint requires a running Session")
            session = self._save_checkpoint(session, "SAVED")
            self._sessions[session.id] = session
            return session

    def suspend(self, session_id, uid):
        with self._lock:
            self._mutable(session_id, uid)
            session = self.status(session_id, uid)
            if session.state != SessionState.RUNNING:
                raise RuntimeFailure("Suspending requires a running Session")
            session = self._save_checkpoint(session, "SUSPENDED")
            self._terminals.close_session(session.id)
            try:
                self.runtime.remove(session.id)
            except Exception as error:
                message = str(error) if isinstance(error, RuntimeFailure) else "Unexpected runtime cleanup failure"
                return self._set(session, SessionState.FAILED, message)
            self._imports.pop(session.id, None)
            self._network_reservations.pop(session.id, None)
            return self._set(session, SessionState.SUSPENDED)

    def discard(self, session_id, uid):
        with self._lock:
            session = self._mutable(session_id, uid)
            if self.practice_store is None:
                raise RuntimeFailure("Practice checkpoint storage is unavailable")
            self.practice_store.delete_checkpoint(session.id)
            if session.state == SessionState.SUSPENDED:
                session = self._set(session, SessionState.STOPPED)
            session = replace(session, checkpoint_at="", updated_at=timestamp())
            self._sessions[session.id] = session
            return session

    def resume(self, session_id, uid):
        with self._lock:
            session = self._mutable(session_id, uid)
            if session.state not in (SessionState.SUSPENDED, SessionState.STOPPED):
                if session.state == SessionState.RUNNING:
                    return session
                raise RuntimeFailure("Resuming requires a suspended or stopped Session with a saved checkpoint")
            if not getattr(session, "checkpoint_at", ""):
                raise RuntimeFailure("Session has no saved checkpoint to resume from")
            if self.practice_store is None:
                raise RuntimeFailure("Practice checkpoint storage is unavailable")
            checkpoint = self.practice_store.get_checkpoint(session.id)
            if checkpoint is None:
                raise RuntimeFailure("Saved checkpoint data not found")
            if session.id not in self._session_packages:
                raise RuntimeFailure(session.error or "Captured Lab package is unavailable")
            self.policy.validate(session.lab)
            self._quota(session.owner_uid, exclude=session.id)
            session = self._set(session, SessionState.PREPARING)
            self._terminals.close_session(session.id)
            try:
                self.runtime.remove(session.id)
            except Exception as error:
                message = str(error) if isinstance(error, RuntimeFailure) else "Unexpected runtime cleanup failure"
                return self._set(session, SessionState.FAILED, message)
            self._imports.pop(session.id, None)
            return self._start(session, workspaces=checkpoint["workspaces"])

    def open_terminal(self, session_id, node_id, uid, sender, rows, columns, slot=0):
        with self._lock:
            session = self.status(session_id, uid)
            if session.state != SessionState.RUNNING:
                raise RuntimeFailure("Terminal requires a running Session")
            if node_id not in {node.id for node in session.lab.nodes}:
                raise TerminalNotFound("Node not found")
            return self._terminals.open(session, node_id, uid, sender, rows, columns, slot)

    def terminal(self, operation, handle, uid, sender, *arguments):
        with self._lock:
            return self._terminals.operate(operation, handle, uid, sender, *arguments)

    def shutdown(self):
        with self._lock:
            self._terminals.close_session()
            self.runtime.cleanup()
            self._imports.clear()
            self._network_reservations.clear()
            self._prepared_submissions.clear()

    def delete_lab(self, lab_id, uid):
        with self._lock:
            self.lab(lab_id)
            for session in self._sessions.values():
                if session.lab.metadata.id == lab_id and session.state != SessionState.STOPPED:
                    raise LabInUseError("Lab has active Sessions; stop them before deleting")
            remove_lab(self.catalog, lab_id)
            if self.practice_store is not None:
                self.practice_store.lab_quizzes.delete_lab(lab_id)
            stopped = [
                sid for sid, session in self._sessions.items()
                if session.lab.metadata.id == lab_id
            ]
            for sid in stopped:
                del self._sessions[sid]
                self._prepared_submissions.pop(sid, None)
                self._session_packages.pop(sid, None)
                self._imports.pop(sid, None)
                if self.practice_store is not None:
                    self.practice_store.delete_checkpoint(sid)
                    self.practice_store.delete_quiz_attempt(sid, 0)
            return True
