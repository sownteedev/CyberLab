#!/usr/bin/env python3
"""Isolated Ubuntu workstation checks; never connects to Docker or the system bus."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dataclasses import asdict, replace
from contextlib import closing
import json
import importlib.util
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch, create_autospec

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "engine"), str(ROOT / "daemon"), str(ROOT / "tools")]
schema_spec = importlib.util.spec_from_file_location("cyberlab.schemas", ROOT / "schemas/__init__.py",
                                                   submodule_search_locations=[str(ROOT / "schemas")])
sys.modules["cyberlab.schemas"] = importlib.util.module_from_spec(schema_spec)
schema_spec.loader.exec_module(sys.modules["cyberlab.schemas"])

from cyberlab.authoring.profiles import image_profiles
from cyberlab.lab.loader import LabValidationError, validate_lab
from cyberlab.lab.models import Network
from cyberlab.lab.workstation import UBUNTU_IMAGE, UBUNTU_USER, WORKSTATION_LABEL, workstation_user
from cyberlab.policy import PolicyDenied, RuntimePolicy
from cyberlab.runtime import RuntimeFailure
from cyberlab.runtime.docker import DockerRuntime
from cyberlab.runtime.checkpoints import CHECKPOINT_LABEL, MAX_IMAGE_BYTES, NODE_LABEL, OWNER_LABEL, SESSION_LABEL, SCOPE_LABEL, validate_images
from cyberlab.service import Engine
from cyberlab.session import Session, SessionState
from cyberlab.session.persistence import PracticeStore
from cyberlabd.config import load_config
from cyberlabd.testing import MemoryRuntime
from tools.admin.prepare_ubuntu_workstation import configured_bytes, RECIPE
from docker import APIClient

def definition():
    return {"apiVersion": "cyberlab.ptit/v1", "kind": "Lab",
            "metadata": {"id": "fixture", "name": "Fixture", "version": "1.0.0"},
            "nodes": [{"id": "client", "image": UBUNTU_IMAGE, "command": ["sleep", "infinity"],
                       "networks": [], "user": asdict(UBUNTU_USER)}], "networks": [], "terminals": ["client"]}

class WorkstationChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="cyberlab-workstation-check-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.document = definition()
        self.lab = validate_lab(self.document)
        self.session = Session("a" * 32, self.lab, 1234, SessionState.RUNNING, "now", "now")
        self.policy = RuntimePolicy(frozenset({UBUNTU_IMAGE}), workstation_images=frozenset({UBUNTU_IMAGE}))
        self.client = Mock()
        self.client.api = create_autospec(APIClient, instance=True)
        self.client.images.get.return_value = SimpleNamespace(id="sha256:" + "b" * 64,
            attrs={"Config": {"Labels": {WORKSTATION_LABEL: "ubuntu-v1"}}})
        self.client.images.list.return_value = []
        self.client.networks.list.return_value = []
        self.client.networks.create.return_value.id = "network"
        self.client.containers.create.return_value.status = "running"
        self.client.containers.create.return_value.id = "container-id"
        self.runtime = DockerRuntime(self.client, self.policy.workstation_images)
        self.runtime.running = Mock(return_value=True)

    def start(self, session=None, **kwargs):
        with patch("cyberlab.runtime.docker.seed_container") as seed:
            self.runtime.start(session or self.session, **kwargs)
            return self.client.containers.create.call_args.kwargs, seed

    def test_policy_requires_administrator_opt_in(self):
        with self.assertRaises(PolicyDenied):
            RuntimePolicy(self.policy.allowed_images).validate(self.lab)
        self.policy.validate(self.lab)

    def test_gui_has_bounded_thread_headroom_without_extra_privileges(self):
        from cyberlab.lab.models import NodeSoftware

        options, _ = self.start()
        self.assertEqual(options['pids_limit'], 256)
        node = replace(self.lab.nodes[0], software=NodeSoftware(gui=True))
        self.runtime.prepared_software = Mock()
        self.runtime.prepared_software.resolve.return_value = 'sha256:' + 'b' * 64
        options, _ = self.start(replace(self.session, lab=replace(self.lab, nodes=(node,))))
        self.assertEqual(options['pids_limit'], 512)
        self.assertEqual(options['shm_size'], '256m')
        self.assertFalse(options['privileged'])
        self.assertEqual(options['cap_drop'], ['ALL'])
        self.assertNotIn('SYS_ADMIN', options['cap_add'])
        self.assertNotIn('seccomp=unconfined', options['security_opt'])

    def test_policy_rejects_wrong_identity_or_unknown_workstation(self):
        for user in (None, replace(UBUNTU_USER, uid=2001)):
            with self.assertRaises(PolicyDenied):
                self.policy.validate(replace(self.lab, nodes=(replace(self.lab.nodes[0], user=user),)))
        with self.assertRaises(PolicyDenied):
            replace(self.policy, workstation_images=frozenset({"ubuntu:latest"})).validate(self.lab)

    def test_profiles_only_expose_enabled_workstation(self):
        self.assertEqual(image_profiles({UBUNTU_IMAGE}), [])
        profile = image_profiles({UBUNTU_IMAGE}, {UBUNTU_IMAGE})[0]
        self.assertTrue(profile["workstation"])
        self.assertEqual(profile["accounts"], [asdict(UBUNTU_USER)])
        self.assertTrue(profile["custom_username"])

    def test_custom_username_validation(self):
        for name in ("son", "alice", "user_2", "user-3", "a" * 32):
            user = workstation_user(name)
            self.assertEqual(user.home, "/home/" + name)
            self.policy.validate(replace(self.lab, nodes=(replace(self.lab.nodes[0], user=user),)))
        for name in ("", "Root", "root", "ubuntu", "nobody", "1user", "_apt", "../son", "a b", "son;id", "$(id)", "a" * 33, "sơn", "alice\n", None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                workstation_user(name)

    def test_custom_user_bootstrap_is_fixed_argv_and_restore_never_renames(self):
        node = replace(self.lab.nodes[0], user=workstation_user("alice"))
        session = replace(self.session, lab=replace(self.lab, nodes=(node,)))
        options, seed = self.start(session)
        self.assertEqual(options["user"], "0:0")
        self.assertEqual(options["working_dir"], "/")
        self.assertEqual(options["command"][3:6], ["cyberlab-user-setup", "alice", "/home/alice"])
        self.assertNotIn("alice", options["command"][2])
        self.assertEqual(options["environment"]["HOME"], "/home/alice")
        self.assertFalse(options["privileged"])
        seed.assert_called_once()
        with patch.object(self.runtime.system_checkpoints, "restore_image", return_value="sha256:" + "e" * 64):
            options, seed = self.start(session, system_images={"client": "sha256:" + "e" * 64})
        self.assertEqual(options["user"], "2000:2000")
        self.assertEqual(options["working_dir"], "/home/alice")
        self.assertNotIn("cyberlab-user-setup", options["command"])
        seed.assert_not_called()

    def test_workstation_args_do_not_grant_host_access(self):
        options, seed = self.start()
        self.assertFalse(options["privileged"])
        self.assertFalse(options["read_only"])
        self.assertEqual(options["cap_drop"], ["ALL"])
        self.assertTrue({"SETUID", "SETGID", "CHOWN"} <= set(options["cap_add"]))
        self.assertFalse({"SYS_ADMIN", "NET_ADMIN", "SYS_PTRACE"} & set(options["cap_add"]))
        self.assertIn("NET_RAW", options["cap_add"])
        self.assertNotIn("volumes", options)
        self.assertNotIn("ports", options)
        self.assertNotIn("/home/student", options["tmpfs"])
        self.assertEqual(options["working_dir"], "/home/student")
        self.assertEqual(options["user"], "2000:2000")
        self.assertFalse(self.client.networks.create.call_args.kwargs["internal"])
        seed.assert_called_once()

    def test_restricted_mode_is_unchanged(self):
        node = replace(self.lab.nodes[0], image="busybox:1.37.0", user=None)
        options, _ = self.start(replace(self.session, lab=replace(self.lab, nodes=(node,))))
        self.assertTrue(options["read_only"])
        self.assertEqual(options["security_opt"], ["no-new-privileges:true"])
        self.assertEqual(options["network_mode"], "none")
        self.assertNotIn("cap_add", options)
        self.client.networks.create.assert_not_called()

    def test_ubuntu_lan_uses_one_network_for_lan_and_internet(self):
        self.document['networks'] = [{'id': 'lan'}]
        self.document['nodes'][0]['networks'] = ['lan']
        lab = validate_lab(self.document)
        self.assertTrue(lab.networks[0].internet)
        options, _ = self.start(replace(self.session, lab=lab))
        self.client.networks.create.assert_called_once()
        self.assertFalse(self.client.networks.create.call_args.kwargs['internal'])
        self.assertTrue(self.client.networks.create.call_args.args[0].endswith('-lan'))
        self.assertEqual(options['network'], 'network')
        self.client.networks.create.return_value.connect.assert_not_called()

    def test_explicit_offline_ubuntu_has_no_hidden_egress(self):
        self.document['networks'] = [{'id': 'lan', 'internet': False}]
        self.document['nodes'][0]['networks'] = ['lan']
        lab = validate_lab(self.document)
        self.assertFalse(lab.networks[0].internet)
        self.start(replace(self.session, lab=lab))
        self.client.networks.create.assert_called_once()
        self.assertTrue(self.client.networks.create.call_args.kwargs['internal'])
        self.client.networks.create.return_value.connect.assert_not_called()

    def test_multi_network_ubuntu_has_only_declared_attachments(self):
        self.document['networks'] = [{'id': 'lan'}, {'id': 'backend'}]
        self.document['nodes'][0]['networks'] = ['lan', 'backend']
        lab = validate_lab(self.document)
        self.assertEqual([network.internet for network in lab.networks], [True, False])
        self.start(replace(self.session, lab=lab))
        self.assertEqual(self.client.networks.create.call_count, 2)
        self.assertEqual([call.kwargs['internal'] for call in self.client.networks.create.call_args_list], [False, True])
        self.client.networks.create.return_value.connect.assert_called_once()

    def test_restricted_legacy_network_stays_internal_unless_explicit(self):
        self.document['nodes'][0].update(image='busybox:1.37.0', networks=['lan'])
        self.document['networks'] = [{'id': 'lan'}]
        self.assertFalse(validate_lab(self.document).networks[0].internet)
        self.document['networks'][0]['internet'] = True
        lab = validate_lab(self.document)
        self.assertTrue(lab.networks[0].internet)
        self.start(replace(self.session, lab=lab))
        self.client.networks.create.assert_called_once()
        self.assertFalse(self.client.networks.create.call_args.kwargs['internal'])

    def test_network_internet_rejects_non_boolean_and_survives_rename(self):
        self.document['networks'] = [{'id': 'lan', 'internet': False}]
        self.document['nodes'][0]['networks'] = ['lan']
        for invalid in ('false', 1, None, [], {}):
            self.document['networks'][0]['internet'] = invalid
            with self.subTest(value=invalid), self.assertRaises(LabValidationError):
                validate_lab(self.document)
        self.document['networks'][0]['internet'] = False
        lab = validate_lab(self.document)
        self.assertFalse(replace(lab.networks[0], id='renamed').internet)
        with self.assertRaises(PolicyDenied):
            self.policy.validate(replace(lab, networks=(Network('lan', internet='false'),)))

    def test_standalone_ubuntu_keeps_one_session_owned_internet_network(self):
        self.start()
        self.client.networks.create.assert_called_once()
        self.assertTrue(self.client.networks.create.call_args.args[0].endswith('--standalone-internet'))
        self.assertEqual(self.client.networks.create.call_args.kwargs['labels']['org.ptit.cyberlab.session'], self.session.id)
        self.assertEqual(self.client.networks.create.call_args.kwargs['options']['com.docker.network.bridge.enable_icc'], 'false')

    def test_network_internet_is_exposed_without_changing_config_tuple(self):
        from cyberlabd.server import configuration_fields

        lab = replace(self.lab, networks=(Network('lan', internet=True), Network('offline')))
        fields = configuration_fields(lab)
        self.assertEqual(fields['network_internet'].value, {'lan': True, 'offline': False})
        self.assertEqual(fields['network_config'].value, [['lan', '', ''], ['offline', '', '']])

    def test_unreviewed_image_and_volumes_are_rejected(self):
        for config in ({"Labels": {}}, {"Labels": {WORKSTATION_LABEL: "ubuntu-v1"}, "Volumes": {"/data": {}}}):
            self.client.images.get.return_value.attrs = {"Config": config}
            with self.assertRaises(RuntimeFailure):
                self.start()
        self.client.containers.create.assert_not_called()

    def test_saved_image_owner_session_and_node_are_checked(self):
        image_id = "sha256:" + "c" * 64
        labels = {CHECKPOINT_LABEL: "v1", OWNER_LABEL: "1234", SESSION_LABEL: self.session.id, NODE_LABEL: "client", SCOPE_LABEL: "production"}
        self.client.images.get.return_value = SimpleNamespace(id=image_id, attrs={"Config": {"Labels": labels}})
        self.assertEqual(self.runtime.system_checkpoints.restore_image(self.session, self.lab.nodes[0], image_id), image_id)
        for key in (OWNER_LABEL, SESSION_LABEL, NODE_LABEL, SCOPE_LABEL):
            with patch.dict(labels, {key: "foreign"}):
                with self.assertRaises(RuntimeFailure):
                    self.runtime.system_checkpoints.restore_image(self.session, self.lab.nodes[0], image_id)

    def test_restore_skips_seed_overwrite(self):
        saved_id = "sha256:" + "c" * 64
        with patch.object(self.runtime.system_checkpoints, "restore_image", return_value=saved_id):
            options, seed = self.start(system_images={"client": saved_id}, workspaces={})
        self.assertEqual(self.client.containers.create.call_args.args[0], saved_id)
        self.assertNotIn("cyberlab-seed", options["command"])
        seed.assert_not_called()
        self.client.images.get.assert_not_called()

    def test_invalid_image_references_are_rejected(self):
        for value in ({"client": "ubuntu:latest"}, {"../host": "sha256:" + "c" * 64}, [], {"client": 1}):
            with self.assertRaises(ValueError):
                validate_images(value)

    def test_checkpoint_size_failure_does_not_stop_container(self):
        self.runtime._workspace_container = Mock(return_value=self.client.containers.create.return_value)
        self.client.api.containers.return_value = [{"Id": "container-id", "SizeRootFs": MAX_IMAGE_BYTES + 1}]
        with self.assertRaises(RuntimeFailure):
            self.runtime.system_checkpoints.capture(self.session)
        self.client.containers.create.return_value.commit.assert_not_called()
        self.client.containers.create.return_value.remove.assert_not_called()

    def test_capture_pauses_and_records_ownership(self):
        container = self.client.containers.create.return_value
        container.commit.return_value.id = "sha256:" + "c" * 64
        self.runtime._workspace_container = Mock(return_value=container)
        self.client.api.containers.return_value = [{"Id": "container-id", "SizeRootFs": 4096}]
        self.assertEqual(self.runtime.system_checkpoints.capture(self.session), {"client": container.commit.return_value.id})
        options = container.commit.call_args.kwargs
        self.assertTrue(options["pause"])
        self.assertEqual(options["conf"]["Labels"][OWNER_LABEL], "1234")

    def test_checkpoint_quota_counts_shared_software_only_once(self):
        from tools.tests.unit.check_image_storage import image
        gib = 1024**3
        self.client.images.list.return_value = [image(str(index), ['ubuntu', 'work-' + str(index)],
                                                       [gib, gib // 2]) for index in range(8)]
        container = self.client.containers.create.return_value
        container.commit.return_value.id = 'sha256:' + 'c' * 64
        self.runtime._workspace_container = Mock(return_value=container)
        self.client.api.containers.return_value = [{'Id': 'container-id', 'SizeRootFs': 4096}]
        self.assertEqual(self.runtime.system_checkpoints.capture(self.session), {'client': container.commit.return_value.id})

    def test_cleanup_never_forces_in_use_images_or_removes_unlabelled_images(self):
        image_id = "sha256:" + "c" * 64
        self.client.images.get.return_value = SimpleNamespace(attrs={"Config": {"Labels": {}}})
        self.runtime.system_checkpoints.release([image_id])
        self.client.images.remove.assert_not_called()
        self.client.images.get.return_value.attrs["Config"]["Labels"][CHECKPOINT_LABEL] = "v1"
        self.client.images.get.return_value.attrs["Config"]["Labels"][SCOPE_LABEL] = "production"
        self.runtime.system_checkpoints.release([image_id])
        self.client.images.remove.assert_called_once_with(image_id, force=False, noprune=True)

    def test_reset_collection_removes_checkpoint_children_before_parents(self):
        from docker.errors import DockerException
        parent_id, child_id = 'sha256:' + 'c' * 64, 'sha256:' + 'd' * 64
        labels = {CHECKPOINT_LABEL: 'v1', SCOPE_LABEL: 'production'}
        images = {
            parent_id: SimpleNamespace(id=parent_id, attrs={'Config': {'Labels': labels},
                                                          'RootFS': {'Layers': ['base', 'save1']}}),
            child_id: SimpleNamespace(id=child_id, attrs={'Config': {'Labels': labels},
                                                        'RootFS': {'Layers': ['base', 'save1', 'save2']}}),
        }
        self.client.images.list.return_value = list(images.values())
        self.client.images.get.side_effect = lambda identifier: images[identifier]

        def remove(identifier, force, noprune):
            self.assertFalse(force)
            self.assertTrue(noprune)
            if identifier == parent_id and child_id in images:
                raise DockerException('image has dependent child images')
            del images[identifier]

        self.client.images.remove.side_effect = remove
        self.runtime.system_checkpoints.collect(set())
        self.assertFalse(images)

    def store(self):
        return PracticeStore(self.root / "practice.sqlite3")

    def test_checkpoint_roundtrip_and_delete(self):
        store = self.store()
        definition_text = json.dumps(self.document)
        images = {"client": "sha256:" + "c" * 64}
        store.save_checkpoint(self.session.id, 1234, "now", "now", "now", "SAVED", definition_text, {},
                              {"definition": definition_text, "assets": {}}, system_images=images)
        self.assertEqual(store.get_checkpoint(self.session.id)["system_images"], images)
        self.assertEqual(store.system_image_ids(), set(images.values()))
        self.assertEqual(store.load_sessions()[0][0].lab.nodes[0].user, UBUNTU_USER)
        store.delete_checkpoint(self.session.id)
        self.assertEqual(store.system_image_ids(), set())

    def test_database_migrates_without_dropping_old_checkpoint(self):
        store = self.store()
        definition_text = json.dumps(self.document)
        store.save_checkpoint("old", 1234, "now", "now", "now", "SAVED", definition_text, {},
                              {"definition": definition_text, "assets": {}})
        with closing(sqlite3.connect(store.database)) as connection:
            with connection:
                connection.execute("ALTER TABLE saved_sessions DROP COLUMN system_images")
                connection.execute("PRAGMA user_version=7")
        migrated = PracticeStore(store.database)
        self.assertEqual(migrated.get_checkpoint("old")["system_images"], {})

    def test_failed_database_save_releases_only_new_capture(self):
        store = self.store()
        engine = Engine(self.root, self.policy, self.runtime, store)
        images = {"client": "sha256:" + "c" * 64}
        self.runtime.system_checkpoints.capture = Mock(return_value=images)
        self.runtime.system_checkpoints.release = Mock()
        with patch.object(store, "save_checkpoint", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                engine._store_checkpoint(self.session, "now", "SAVED", {}, {"definition": json.dumps(self.document), "assets": {}})
        self.runtime.system_checkpoints.release.assert_called_once()
        self.assertEqual(list(self.runtime.system_checkpoints.release.call_args.args[0]), list(images.values()))
        self.client.containers.create.return_value.remove.assert_not_called()

    def test_invalid_checkpoint_definition_never_creates_image(self):
        engine = Engine(self.root, self.policy, self.runtime, self.store())
        self.runtime.system_checkpoints.capture = Mock(return_value={'client': 'sha256:' + 'c' * 64})
        with self.assertRaisesRegex(RuntimeFailure, 'definition is invalid'):
            engine._store_checkpoint(self.session, 'now', 'SAVED', {}, {'definition': '{}', 'assets': {}})
        self.runtime.system_checkpoints.capture.assert_not_called()

    def test_config_is_explicit_and_preserves_catalog_and_users(self):
        original = {"catalog": str(self.root), "allowed_uids": [1234], "allowed_images": ["busybox:1.37.0"], "authoring": True}
        target = self.root / "daemon.toml"
        target.write_bytes(configured_bytes(original))
        with patch("cyberlabd.config.trusted_path"):
            config = load_config(target)
        self.assertEqual(config.workstation_images, {UBUNTU_IMAGE})
        self.assertEqual(config.catalog, self.root)
        self.assertEqual(config.allowed_uids, {1234})
        target.write_text(target.read_text().replace('workstation_images = ["cyberlab/ubuntu:24.04-1"]', 'workstation_images = ["untrusted:latest"]'))
        with patch("cyberlabd.config.trusted_path"), self.assertRaises(ValueError):
            load_config(target)

    def test_recipe_is_fixed_non_root_and_uses_no_host_mounts(self):
        recipe = RECIPE.format(base="sha256:" + "d" * 64)
        self.assertIn("USER 2000:2000", recipe)
        self.assertIn("NOPASSWD: ALL", recipe)
        self.assertIn("--no-create-home", recipe)
        self.assertNotIn("VOLUME", recipe)
        self.assertNotIn("--mount", recipe)

    def test_restricted_session_save_suspend_resume_and_reset(self):
        document = definition()
        document["nodes"][0].update(image="busybox:1.37.0")
        del document["nodes"][0]["user"]
        package = self.root / "fixture"
        package.mkdir()
        (package / "lab.yaml").write_text(json.dumps(document))
        store = self.store()
        runtime = MemoryRuntime()
        policy = RuntimePolicy(frozenset({"busybox:1.37.0"}))
        engine = Engine(self.root, policy, runtime, store)
        session = engine.start("fixture", 1234)
        self.assertEqual(session.state, SessionState.RUNNING)
        runtime.files[session.id]["client"]["kept.txt"] = b"saved"
        self.assertEqual(engine.suspend(session.id, 1234).state, SessionState.SUSPENDED)
        restored = Engine(self.root, policy, runtime, store)
        self.assertEqual(restored.resume(session.id, 1234).state, SessionState.RUNNING)
        self.assertEqual(runtime.files[session.id]["client"]["kept.txt"], b"saved")
        self.assertEqual(store.get_checkpoint(session.id)["system_images"], {})
        self.assertEqual(restored.reset(session.id, 1234).state, SessionState.RUNNING)
        self.assertNotIn("kept.txt", runtime.files[session.id]["client"])

    def test_failed_system_capture_keeps_running_session_and_old_checkpoint(self):
        store = self.store()
        engine = Engine(self.root, self.policy, self.runtime, store)
        engine._sessions[self.session.id] = self.session
        engine._session_packages[self.session.id] = {"definition": json.dumps(self.document), "assets": {}}
        self.runtime.system_checkpoints.capture = Mock(side_effect=RuntimeFailure("disk quota"))
        with self.assertRaisesRegex(RuntimeFailure, "disk quota"):
            engine.suspend(self.session.id, 1234)
        self.assertEqual(engine._sessions[self.session.id].state, SessionState.RUNNING)
        self.client.containers.create.return_value.remove.assert_not_called()

    def test_checkpoint_collection_preserves_referenced_ids_and_other_scopes(self):
        kept_id = "sha256:" + "d" * 64
        stale_id = "sha256:" + "e" * 64
        self.client.images.list.return_value = [SimpleNamespace(id=kept_id, attrs={}), SimpleNamespace(id=stale_id, attrs={})]
        self.runtime.system_checkpoints.release = Mock()
        self.runtime.system_checkpoints.collect({kept_id})
        self.assertEqual(list(self.runtime.system_checkpoints.release.call_args.args[0]), [stale_id])
        self.assertIn(f"{SCOPE_LABEL}=production", self.client.images.list.call_args.kwargs["filters"]["label"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
