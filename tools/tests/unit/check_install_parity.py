"""Fresh-install parity checks using temporary files; no Docker or system changes."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from copy import deepcopy
import json
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import nullcontext
import stat
import subprocess
from unittest.mock import Mock

from tools.install import runtime_admin as admin
from tools.admin import prepare_ubuntu_workstation as ubuntu


def reviewed_image():
    return {"Id": "sha256:" + "a" * 64, "Config": {
        "Labels": {ubuntu.LABEL: "ubuntu-v1"}, "Volumes": None,
        "User": "2000:2000", "WorkingDir": "/home/student",
        "Entrypoint": None, "Cmd": ["sleep", "infinity"],
    }}


class FreshInstallChecks(unittest.TestCase):
    def test_prepare_ubuntu_is_an_explicit_exclusive_installer_operation(self):
        entry = Path(__file__).resolve().parents[3] / "install.sh"
        help_result = subprocess.run(["bash", str(entry), "--help"], capture_output=True, text=True, timeout=10)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--prepare-ubuntu", help_result.stdout)
        for options in (("--prepare-ubuntu", "--update"), ("--prepare-ubuntu", "--no-deps"),
                        ("--prepare-ubuntu", "--offline")):
            result = subprocess.run(["bash", str(entry), *options], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Unknown option", result.stderr)

    def test_new_config_enables_ubuntu_and_busybox(self):
        account = SimpleNamespace(pw_uid=1000)
        catalog, config, dropin = admin.configuration(account)
        document = tomllib.loads(config.decode())
        self.assertEqual(document["allowed_images"], [admin.IMAGE, ubuntu.IMAGE])
        self.assertEqual(document["workstation_images"], [ubuntu.IMAGE])
        self.assertEqual(document["catalog"], str(catalog))
        self.assertNotIn(b"/home/", dropin)

    def test_fresh_prepare_builds_ubuntu_after_docker_safety_checks(self):
        account = SimpleNamespace(pw_uid=1000)
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            with patch.object(admin, "run", return_value=SimpleNamespace(stdout="", returncode=0)), \
                 patch.object(admin, "tool") as helper:
                admin.docker_preflight(account, stage)
            helper.assert_called_once_with("prepare_ubuntu_workstation", directory="admin")
            helper.return_value.prepare_image.assert_called_once_with(stage)

    def test_missing_ubuntu_profile_fails_fresh_verification(self):
        def run(*arguments, **kwargs):
            if arguments[1:] == ("info",):
                return SimpleNamespace(returncode=0, stdout=json.dumps({"capabilities": [
                    "runtime:docker", "authoring", "terminal", "checkwork", "quiz",
                    "lab-package-import", "lab-package-export", "session-persistence",
                    "machine-setup-v1", "seamless-apps"]}))
            if arguments[1:] == ("draft", "info"):
                return SimpleNamespace(returncode=0, stdout=json.dumps({"image_profiles": [],
                    "machine_setup": True, "software_preparation": True}))
            return SimpleNamespace(returncode=0, stdout="[]")
        with patch.object(admin, "run", side_effect=run):
            with self.assertRaisesRegex(RuntimeError, "Ubuntu"):
                admin.verify_daemon(SimpleNamespace(pw_uid=1000), require_workstation=True)


class UbuntuPreparationChecks(unittest.TestCase):
    def test_existing_valid_image_is_reused_without_pull_or_build(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(ubuntu, "docker", return_value="existing\n") as docker, \
             patch.object(ubuntu, "inspect_image", return_value=reviewed_image()):
            receipt = ubuntu.prepare_image(Path(directory))
        self.assertEqual(receipt["image_id"], reviewed_image()["Id"])
        self.assertEqual(receipt["action"], "reused")
        self.assertTrue(all(call.args[0] == "image" for call in docker.call_args_list))

    def test_existing_unreviewed_image_is_never_overwritten(self):
        for field, value in (("Labels", {}), ("Volumes", {"/data": {}}),
                             ("User", "root"), ("Entrypoint", ["/unexpected"]),
                             ("WorkingDir", "/root"), ("Cmd", ["sh"])):
            image = deepcopy(reviewed_image())
            image["Config"][field] = value
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory, \
                 patch.object(ubuntu, "docker", return_value="existing\n") as docker, \
                 patch.object(ubuntu, "inspect_image", return_value=image):
                with self.assertRaisesRegex(ValueError, "reviewed"):
                    ubuntu.prepare_image(Path(directory))
                self.assertTrue(all(call.args[0] == "image" for call in docker.call_args_list))

    def test_build_pins_base_and_copies_only_fixed_recipe(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            base = {"Id": "sha256:" + "b" * 64, "RepoDigests": ["ubuntu@sha256:" + "c" * 64]}
            with patch.object(ubuntu, "docker", return_value="") as docker, \
                 patch.object(ubuntu, "check_build_space"), \
                 patch.object(ubuntu, "inspect_image", side_effect=[base, reviewed_image()]):
                receipt = ubuntu.prepare_image(stage)
            build = next(call for call in docker.call_args_list if call.args[0] == "build")
            context = Path(build.args[-1])
            self.assertEqual(list(context.iterdir()), [context / "Dockerfile"])
            recipe = (context / "Dockerfile").read_text()
            self.assertTrue(recipe.startswith("FROM " + base["Id"] + "\n"))
            self.assertEqual(receipt["action"], "built")
            self.assertNotIn("--privileged", build.args)

    def test_low_space_stops_before_pull_or_build(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(ubuntu, "docker", side_effect=["", directory]) as docker, \
             patch.object(ubuntu.shutil, "disk_usage", return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(ValueError, "space"):
                ubuntu.prepare_image(Path(directory))
            self.assertFalse(any(call.args[0] in {"pull", "build"} for call in docker.call_args_list))

    def test_invalid_pulled_base_id_is_not_used_in_recipe(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(ubuntu, "docker", return_value="") as docker, \
             patch.object(ubuntu, "check_build_space"), \
             patch.object(ubuntu, "inspect_image", return_value={"Id": "ubuntu:latest\nRUN unexpected"}):
            with self.assertRaisesRegex(ValueError, "identity"):
                ubuntu.prepare_image(Path(directory))
            self.assertFalse(any(call.args[0] == "build" for call in docker.call_args_list))


class ExistingInstallChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.stage = Path(self.temporary.name)
        self.config = self.stage / "daemon.toml"
        self.original = b'catalog = "/private/labs"\nallowed_uids = [1000, 2000]\nallowed_images = ["busybox:1.37.0"]\nauthoring = true\n'
        self.config.write_bytes(self.original)
        self.config.chmod(0o600)
        self.enterContext(patch.object(ubuntu.guarded, "CONFIG", self.config))
        self.enterContext(patch.object(ubuntu.guarded, "check_admin_path"))
        self.locks = self.enterContext(patch.object(ubuntu.guarded, "installer_lock", side_effect=lambda *args, **kwargs: nullcontext()))
        self.studio = self.enterContext(patch.object(ubuntu.guarded, "check_studio_closed"))
        self.enterContext(patch.object(ubuntu.guarded, "wait_for_daemon", return_value={"capabilities": ["maintenance-lock-v1", "runtime:docker"]}))
        self.enterContext(patch.object(ubuntu.guarded, "stopped_checkpoints", return_value={}))
        self.run = self.enterContext(patch.object(ubuntu.guarded, "run"))
        self.enterContext(patch.object(ubuntu, "inspect_image", return_value=reviewed_image()))
        self.prepare = self.enterContext(patch.object(ubuntu, "prepare_image"))
        self.cli = self.enterContext(patch.object(ubuntu.guarded, "cli", side_effect=self.reply))

    def reply(self, uid, *arguments):
        if arguments == ("sessions",):
            return []
        if arguments == ("labs",):
            return [{"id": "kept"}]
        return {"workstation_runtime": True, "machine_setup": True, "software_preparation": True,
                "image_profiles": [{"image": ubuntu.IMAGE, "workstation": True}]}

    def test_explicit_preparation_preserves_config_and_private_permissions(self):
        ubuntu.prepare_existing(1000, self.stage, lock_fd=9)
        changed = tomllib.loads(self.config.read_text())
        self.assertEqual(changed["catalog"], "/private/labs")
        self.assertEqual(changed["allowed_uids"], [1000, 2000])
        self.assertEqual(changed["workstation_images"], [ubuntu.IMAGE])
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertEqual((self.stage / "daemon.toml.before").read_bytes(), self.original)
        self.assertEqual(stat.S_IMODE((self.stage / "daemon.toml.before").stat().st_mode), 0o600)
        self.locks.assert_any_call(9)
        self.locks.assert_any_call(path=ubuntu.guarded.MAINTENANCE_LOCK)

    def test_another_users_running_session_blocks_before_build(self):
        self.cli.side_effect = lambda uid, *args: [{"state": "RUNNING"}] if uid == 2000 and args == ("sessions",) else self.reply(uid, *args)
        with self.assertRaisesRegex(ValueError, "Sessions"):
            ubuntu.prepare_existing(1000, self.stage)
        self.prepare.assert_not_called()
        self.run.assert_not_called()
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_open_studio_blocks_before_build(self):
        self.studio.side_effect = ValueError("Studio open")
        with self.assertRaisesRegex(ValueError, "Studio"):
            ubuntu.prepare_existing(1000, self.stage)
        self.prepare.assert_not_called()
        self.run.assert_not_called()

    def test_build_failure_does_not_stop_daemon_or_change_config(self):
        self.prepare.side_effect = RuntimeError("build failed")
        with self.assertRaisesRegex(RuntimeError, "build failed"):
            ubuntu.prepare_existing(1000, self.stage)
        self.run.assert_not_called()
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_failed_activation_restores_exact_config(self):
        policies = iter([self.reply(1000, "draft", "info"), {"image_profiles": []}])
        self.cli.side_effect = lambda uid, *args: next(policies) if args == ("draft", "info") else self.reply(uid, *args)
        with self.assertRaisesRegex(RuntimeError, "verification"):
            ubuntu.prepare_existing(1000, self.stage)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertGreaterEqual(sum(call.args[1] == "start" for call in self.run.call_args_list), 2)

    def test_cancellation_after_config_write_restores_original(self):
        starts = 0
        def run(*arguments, **kwargs):
            nonlocal starts
            if arguments[1] == "start":
                starts += 1
                if starts == 1:
                    raise KeyboardInterrupt()
        self.run.side_effect = run
        with self.assertRaises(KeyboardInterrupt):
            ubuntu.prepare_existing(1000, self.stage)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertEqual(starts, 2)

    def test_missing_maintenance_barrier_blocks_build_and_policy_change(self):
        with patch.object(ubuntu.guarded, "wait_for_daemon", return_value={"capabilities": ["runtime:docker"]}):
            with self.assertRaisesRegex(ValueError, "maintenance"):
                ubuntu.prepare_existing(1000, self.stage)
        self.prepare.assert_not_called()
        self.run.assert_not_called()

    def test_unknown_config_fields_are_not_silently_erased(self):
        original = self.original + b'custom = "keep"\n'
        self.config.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "Unknown config"):
            ubuntu.prepare_existing(1000, self.stage)
        self.assertEqual(self.config.read_bytes(), original)
        self.prepare.assert_not_called()

    def test_background_preparation_blocks_before_build(self):
        with patch.object(ubuntu.guarded, "wait_for_daemon", return_value={"capabilities": ["runtime:docker", "maintenance-lock-v1", "maintenance-busy"]}):
            with self.assertRaisesRegex(ValueError, "background"):
                ubuntu.prepare_existing(1000, self.stage)
        self.prepare.assert_not_called()
        self.run.assert_not_called()

    def test_concurrent_config_change_is_not_overwritten(self):
        concurrent = self.original + b"# admin changed settings\n"
        self.prepare.side_effect = lambda *_: self.config.write_bytes(concurrent)
        with self.assertRaisesRegex(ValueError, "Configuration changed"):
            ubuntu.prepare_existing(1000, self.stage)
        self.assertEqual(self.config.read_bytes(), concurrent)
        self.run.assert_not_called()

    def test_already_enabled_is_verified_without_restart(self):
        current = ubuntu.configured_bytes(tomllib.loads(self.original.decode()))
        self.config.write_bytes(current)
        ubuntu.prepare_existing(1000, self.stage)
        self.assertEqual(self.config.read_bytes(), current)
        self.run.assert_not_called()


class XpraPrerequisiteChecks(unittest.TestCase):
    def test_missing_cairo_bridge_is_not_reported_ready(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "cli"))
        from cyberlab_cli.xpra_client import probe
        modules = {"xpra": SimpleNamespace(__version__="3.1.5"),
                   "xpra.net.rencodeplus": SimpleNamespace(rencodeplus=SimpleNamespace(dumps=lambda _: b"")),
                   "gi": SimpleNamespace(require_version=Mock(), require_foreign=Mock(side_effect=ImportError("cairo bridge missing")))}
        with patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(ImportError, "cairo"):
                probe()


if __name__ == "__main__":
    unittest.main()
