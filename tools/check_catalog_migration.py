"""Isolated catalog migration checks; never accesses the real catalog."""

from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import migrate_catalog as migration


class CatalogMigrationChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "old"
        self.source.mkdir()

    def test_copy_retains_binary_empty_directories_and_private_modes(self):
        (self.source / "empty").mkdir()
        (self.source / "payload").write_bytes(bytes(range(256)))
        destination = self.root / "new"
        before = migration.tree_digest(self.source)
        migration.copy_catalog(self.source, destination)
        self.assertEqual(before, migration.tree_digest(destination))
        self.assertEqual(before, migration.tree_digest(self.source))
        self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
        self.assertEqual((destination / "empty").stat().st_mode & 0o777, 0o700)
        self.assertEqual((destination / "payload").stat().st_mode & 0o777, 0o600)

    def test_rejects_symlinks_hardlinks_and_special_files(self):
        external = self.root / "outside"
        external.write_bytes(b"private")
        entry = self.source / "entry"
        for kind in ("file-link", "directory-link", "hardlink", "fifo"):
            with self.subTest(kind=kind):
                if kind == "file-link":
                    entry.symlink_to(external)
                elif kind == "directory-link":
                    entry.symlink_to(self.root, target_is_directory=True)
                elif kind == "hardlink":
                    os.link(external, entry)
                else:
                    os.mkfifo(entry)
                try:
                    with self.assertRaises(ValueError):
                        migration.tree_digest(self.source)
                finally:
                    entry.unlink()

    def test_existing_destination_never_overwritten(self):
        destination = self.root / "new"
        destination.mkdir()
        (destination / "keep").write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            migration.copy_catalog(self.source, destination)
        self.assertEqual((destination / "keep").read_bytes(), b"keep")

    def test_source_root_cannot_be_a_symlink(self):
        alias = self.root / "alias"
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(OSError):
            migration.tree_digest(alias)

    def test_size_and_entry_limits(self):
        (self.source / "file").write_bytes(b"1234")
        with patch.object(migration, "MAX_BYTES", 3), self.assertRaisesRegex(ValueError, "size"):
            migration.tree_digest(self.source)
        with patch.object(migration, "MAX_FILES", 0), self.assertRaisesRegex(ValueError, "entry count"):
            migration.tree_digest(self.source)

    def test_config_without_top_level_catalog_refused(self):
        with self.assertRaisesRegex(ValueError, "catalog setting"):
            migration.catalog_config(b'allowed_uids = [1000]\n', self.root)

    def test_non_root_migration_does_not_change_anything(self):
        with patch.object(migration.os, "geteuid", return_value=1000), \
             patch.object(migration.updater, "run") as run:
            with self.assertRaisesRegex(ValueError, "sudo"):
                migration.migrate(1000)
            run.assert_not_called()

    def test_config_only_changes_catalog(self):
        original = b'catalog = "/old" # keep other settings\nallowed_uids = [1000, 1001]\nauthoring = true\n'
        changed = tomllib.loads(migration.catalog_config(original, self.root).decode())
        expected = tomllib.loads(original.decode())
        expected["catalog"] = str(self.root)
        self.assertEqual(changed, expected)

    def test_transaction_verifies_and_restores_on_failure(self):
        for fails in (False, "permissions", "start", "catalog", "sessions", "write"):
            with self.subTest(fails=fails), tempfile.TemporaryDirectory(dir=self.root) as directory:
                root = Path(directory)
                config = root / "daemon.toml"
                dropin = root / "authoring.conf"
                config.write_bytes(b"old config")
                dropin.write_bytes(b"old policy")
                staged = root / "staged"
                staged.mkdir()
                destination = root / "labs"
                replacements = [(config, b"new config", 0o600), (dropin, b"new policy", 0o644)]
                with ExitStack() as stack:
                    run = stack.enter_context(patch.object(migration.updater, "run"))
                    stack.enter_context(patch.object(migration.updater, "check_stored_sessions"))
                    stack.enter_context(patch.object(migration.updater, "check_studio_closed"))
                    stack.enter_context(patch.object(migration.updater, "wait_for_daemon", return_value={}))
                    cli = stack.enter_context(patch.object(migration.updater, "cli", return_value=[]))
                    sessions = stack.enter_context(patch.object(migration.updater, "stopped_checkpoints", return_value={}))
                    check = stack.enter_context(patch.object(migration, "verify_private_catalog"))
                    if fails:
                        if fails == "permissions":
                            check.side_effect = RuntimeError("injected verification failure")
                        elif fails == "start":
                            failed_once = False
                            def fail_first_start(*arguments, **kwargs):
                                nonlocal failed_once
                                if "start" in arguments and not failed_once:
                                    failed_once = True
                                    raise RuntimeError("injected start failure")
                            run.side_effect = fail_first_start
                        elif fails == "catalog":
                            cli.return_value = [{"id": "extra", "name": "extra", "version": "1"}]
                        elif fails == "sessions":
                            sessions.return_value = {"unexpected": {"id": "unexpected"}}
                        elif fails == "write":
                            replace = migration.updater.replace_file
                            def fail_policy(path, content, mode):
                                if path == dropin and content == b"new policy":
                                    raise RuntimeError("injected write failure")
                                replace(path, content, mode)
                            stack.enter_context(patch.object(migration.updater, "replace_file", side_effect=fail_policy))
                        with self.assertRaisesRegex(RuntimeError, "restored"):
                            migration.activate(staged, destination, replacements, 1000, [1000], {}, [])
                        self.assertEqual(config.read_bytes(), b"old config")
                        self.assertEqual(dropin.read_bytes(), b"old policy")
                    else:
                        migration.activate(staged, destination, replacements, 1000, [1000], {}, [])
                        self.assertEqual(config.read_bytes(), b"new config")
                    self.assertTrue(destination.is_dir())
                    self.assertTrue(self.source.is_dir())
                    self.assertTrue(any("start" in call.args for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
