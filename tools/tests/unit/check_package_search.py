#!/usr/bin/env python3
"""Bounded Ubuntu metadata search checks; no network or Docker."""
from hashlib import sha256
import lzma
from pathlib import Path
import sys
from threading import Event
from time import monotonic, sleep
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "engine"))
from cyberlab.authoring.packages import PackageSearch, parse_packages, release_entries


class PackageSearchChecks(unittest.TestCase):
    def setUp(self):
        self.data = lzma.compress(b"Package: mousepad\nArchitecture: amd64\nDescription: Simple text editor\n\nPackage: snapshots\nArchitecture: all\nDescription: Snapshot utility\n\nPackage: foreign\nArchitecture: arm64\nDescription: Foreign architecture\n\nPackage: snapd\nArchitecture: amd64\nDescription: Snap daemon\n\n")
        self.digest = sha256(self.data).hexdigest()
        self.release = ("SHA256:\n" + "".join(" " + self.digest + " " + str(len(self.data)) + " " + component + "/binary-amd64/Packages.xz\n" for component in ("main", "universe", "restricted", "multiverse"))).encode()
        self.calls = []
        self.index = PackageSearch(fetch=self.fetch, machine="x86_64")

    def fetch(self, url, limit, deadline):
        self.calls.append(url)
        if url.startswith("https://packages.mozilla.org/"):
            return ("SHA256:\n " + sha256(b"\n").hexdigest() + " 1 main/binary-amd64/Packages\n").encode() if url.endswith("Release") else b"\n"
        return self.release if url.endswith("Release") else self.data

    def load(self):
        self.index.attempted_at = monotonic()
        self.index._load()
        self.assertFalse(self.index.error)

    def test_metadata_covers_release_updates_security_and_components(self):
        self.load()
        self.assertEqual(len(self.calls), 17)
        self.assertTrue(any("noble-security" in url for url in self.calls))
        self.assertTrue(any("noble-updates" in url for url in self.calls))
        self.assertTrue(all(url.startswith("https://") for url in self.calls))
        self.assertEqual(set(self.index.entries), {"mousepad", "snapshots", "snapd"})

    def test_query_matches_description_and_partial_names(self):
        self.load()
        result = self.index.search("text editor")
        self.assertIn("mousepad", [entry["id"] for entry in result["packages"]])
        self.assertEqual(self.index.search("mouse")["packages"][0]["id"], "mousepad")
        self.assertEqual(self.index.search("soan thao")["packages"][0]["id"], "mousepad")
        self.assertIn("mousepad", [entry["id"] for entry in self.index.search("soạn thảo")["packages"]])
        self.assertTrue(result["cached"])
        self.assertEqual(result["state"], "ready")
        self.assertEqual(len(self.calls), 17)

    def test_empty_query_starts_repository_browse_without_inventing_results(self):
        with patch("cyberlab.authoring.packages.Thread") as thread:
            result = self.index.search("")
        thread.return_value.start.assert_called_once()
        self.assertEqual(result["state"], "loading")
        self.assertEqual(result["packages"], [])

    def test_only_repository_entries_are_returned(self):
        self.load()
        self.assertEqual({entry["id"] for entry in self.index.search("")["packages"]}, {"mousepad", "snapshots", "snapd"})
        for query in ("ping", "python", "firefox", "wireshark", "nano"):
            self.assertEqual(self.index.search(query)["packages"], [])

    def test_repository_names_and_descriptions_are_not_replaced(self):
        self.index.entries = {name: {"id": name, "name": name, "description": "Repository description"}
                              for name in ("iputils-ping", "python3", "wireshark")}
        self.index.loaded_at = monotonic()
        for name, query in (("iputils-ping", "ping"), ("python3", "python"), ("wireshark", "wireshark")):
            entry = self.index.search(query)["packages"][0]
            self.assertEqual(entry["name"], name)
            self.assertEqual(entry["description"], "Repository description")
            self.assertEqual(bool(entry.get("application")), name == "wireshark")

    def test_policy_catalog_does_not_offer_curated_packages(self):
        from cyberlab.lab.software import catalog
        self.assertEqual(catalog()["packages"], [])

    def test_snap_packages_remain_visible_with_installation_reason(self):
        data = lzma.compress(b"Package: firefox\nArchitecture: amd64\nDescription: Transitional package - firefox -> firefox snap\nDepends: snapd (>= 2)\n\nPackage: chromium-browser\nArchitecture: amd64\nDescription: Browser\nDepends: snapd:amd64\n\nPackage: snapd\nArchitecture: amd64\nDescription: Snap daemon\n\nPackage: tshark\nArchitecture: amd64\nDescription: Packet analyzer\n\nPackage: wireshark-common\nArchitecture: amd64\nDescription: Common files\n\n")
        self.index.entries = parse_packages(data, "amd64", monotonic() + 5)
        self.index.loaded_at = monotonic()
        self.assertEqual(set(self.index.entries), {"firefox", "chromium-browser", "snapd", "tshark", "wireshark-common"})
        for name in self.index.entries:
            entry = self.index.search(name)["packages"][0]
            self.assertFalse(entry["installable"])
            self.assertTrue(entry["unavailable_reason"])
            self.assertEqual(entry["source"], "ubuntu")

    def test_mozilla_firefox_is_verified_separate_and_does_not_replace_ubuntu(self):
        self.mozilla = b"Package: firefox\nArchitecture: amd64\nDescription: Firefox web browser\n\nPackage: thunderbird\nArchitecture: amd64\nDescription: Mail client\n\n"
        mozilla_release = ("SHA256:\n " + sha256(self.mozilla).hexdigest() + " " + str(len(self.mozilla)) + " main/binary-amd64/Packages\n").encode()
        def fetch(url, limit, deadline):
            if url.startswith("https://packages.mozilla.org/"):
                return mozilla_release if url.endswith("Release") else self.mozilla
            return self.fetch(url, limit, deadline)
        self.index.fetch = fetch
        self.load()
        self.index.entries["firefox"] = {"id": "firefox", "name": "firefox", "description": "Transitional package to Snap", "requires_snap": True}
        entries = self.index.search("firefox")["packages"]
        self.assertEqual([(entry["id"], entry["source"]) for entry in entries], [("firefox", "mozilla"), ("firefox", "ubuntu")])
        self.assertTrue(entries[0]["installable"])
        self.assertTrue(entries[0]["application"])
        self.assertFalse(entries[1]["installable"])
        self.assertEqual(self.index.search("thunderbird")["packages"], [])

    def test_mozilla_failure_keeps_ubuntu_and_does_not_fabricate_firefox(self):
        def fetch(url, limit, deadline):
            if url.startswith("https://packages.mozilla.org/"):
                raise OSError("offline")
            return self.fetch(url, limit, deadline)
        self.index.fetch = fetch
        with self.assertLogs("cyberlab.authoring.packages", level="WARNING"):
            self.load()
        result = self.index.search("mouse")
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["source_errors"], ["mozilla"])
        self.assertEqual(result["packages"][0]["id"], "mousepad")
        self.assertEqual(self.index.search("firefox")["packages"], [])

    def test_mozilla_checksum_mismatch_retains_previous_verified_entry(self):
        previous = {"firefox": {"id": "firefox", "name": "firefox", "description": "Cached browser"}}
        self.index.mozilla_entries = previous
        def fetch(url, limit, deadline):
            if url.startswith("https://packages.mozilla.org/"):
                return b"SHA256:\n " + b"0" * 64 + b" 3 main/binary-amd64/Packages\n" if url.endswith("Release") else b"bad"
            return self.fetch(url, limit, deadline)
        self.index.fetch = fetch
        with self.assertLogs("cyberlab.authoring.packages", level="WARNING"):
            self.load()
        self.assertIs(self.index.mozilla_entries, previous)
        result = self.index.search("firefox")
        self.assertEqual(result["source_errors"], ["mozilla"])
        self.assertEqual(result["packages"][0]["description"], "Cached browser")

    def test_bad_checksum_retains_previous_cache(self):
        self.load()
        previous = self.index.entries
        self.index.fetch = lambda url, limit, deadline: self.release if url.endswith("Release") else b"bad"
        with self.assertLogs("cyberlab.authoring.packages", level="WARNING"):
            self.index._load()
        self.assertIs(self.index.entries, previous)
        self.assertEqual(self.index.search("mouse")["state"], "error")
        self.assertEqual(self.index.search("mouse")["packages"][0]["id"], "mousepad")

    def test_bad_query_and_unsupported_architecture(self):
        for query in ("x" * 101, "foo\nbar", None):
            with self.assertRaises(ValueError):
                self.index.search(query)
        unsupported = PackageSearch(fetch=self.fetch, machine="unsupported")
        self.assertEqual(unsupported.search("editor")["state"], "error")
        self.assertFalse(self.calls)

    def test_result_bound_and_exact_rank(self):
        self.index.entries = {"editor" + str(index): {"id": "editor" + str(index), "name": "editor" + str(index), "description": "Text editor"} for index in range(100)}
        self.index.loaded_at = monotonic()
        result = self.index.search("editor99")
        self.assertEqual(result["packages"][0]["id"], "editor99")
        self.assertEqual(len(self.index.search("editor")["packages"]), 40)

    def test_package_name_matches_rank_before_description_substrings(self):
        self.index.entries = {"map" + str(number): {"id": "map" + str(number), "name": "map" + str(number), "description": "Mapping tools"} for number in range(60)}
        self.index.entries["iputils-ping"] = {"id": "iputils-ping", "name": "iputils-ping", "description": "Tools to test network connectivity"}
        self.index.loaded_at = monotonic()
        self.assertEqual(self.index.search("ping")["packages"][0]["id"], "iputils-ping")

    def test_load_is_single_flight_and_nonblocking(self):
        gate = Event()
        started = Event()
        def fetch(url, limit, deadline):
            started.set()
            gate.wait(2)
            return self.fetch(url, limit, deadline)
        self.index.fetch = fetch
        try:
            self.assertEqual(self.index.search("mouse")["state"], "loading")
            self.assertTrue(started.wait(1))
            for attempt in range(4):
                self.assertEqual(self.index.search("mouse", True)["state"], "loading")
        finally:
            gate.set()
        deadline = monotonic() + 3
        while self.index.loading and monotonic() < deadline:
            sleep(.01)
        self.assertFalse(self.index.loading)
        self.assertEqual(len(self.calls), 17)

    def test_expansion_limit_truncation_and_long_apt_fields(self):
        with patch("cyberlab.authoring.packages.MAX_EXPANDED", 10), self.assertRaises(ValueError):
            parse_packages(self.data, "amd64", monotonic() + 5)
        with self.assertRaises((ValueError, lzma.LZMAError)):
            parse_packages(self.data[:-10], "amd64", monotonic() + 5)
        long_field = lzma.compress(b"Package: mousepad\nArchitecture: amd64\nDepends: " + b"a" * 20000 + b"\nDescription: Text editor\n\n")
        self.assertIn("mousepad", parse_packages(long_field, "amd64", monotonic() + 5))
        with self.assertRaises(ValueError):
            parse_packages(self.data, "amd64", monotonic() - 1)

    def test_release_sha256_section(self):
        result = release_entries(self.release + b"SHA512:\n ignored\n")
        self.assertEqual(len(result), 4)
        self.assertEqual(result["main/binary-amd64/Packages.xz"], (self.digest, len(self.data)))

    def test_concatenated_xz_streams_used_by_ubuntu(self):
        data = self.data + b"\x00" * 4 + lzma.compress(b"Package: another-editor\nArchitecture: all\nDescription: Another text editor\n\n")
        self.assertIn("another-editor", parse_packages(data, "amd64", monotonic() + 5))

    def test_cli_checks_authoring_policy_before_unprivileged_lookup(self):
        import argparse
        import asyncio
        import json

        root = Path(__file__).resolve().parents[3]
        sys.path[:0] = [str(root / "cli"), str(root / "daemon")]
        from cyberlab_cli import drafts
        parser = argparse.ArgumentParser()
        drafts.add_parser(parser.add_subparsers())
        arguments = parser.parse_args(["draft", "software-search", "text editor", "--refresh"])
        self.assertIsNone(drafts.prepare(arguments))
        async def request(bus, member, body):
            self.assertEqual(member, "GetAuthoringInfo")
            self.assertEqual(body, [])
            return json.dumps({"software_search": True})
        with patch("cyberlab_cli.package_search.search", return_value={"state": "ready", "packages": []}) as lookup:
            result = asyncio.run(drafts.run(None, request, arguments, None))
            lookup.assert_called_once_with("text editor", True)
        self.assertEqual(result["state"], "ready")


class UserCacheChecks(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile
        root = Path(__file__).resolve().parents[3]
        sys.path[:0] = [str(root / "cli"), str(root / "daemon")]
        from cyberlab_cli import package_search
        self.module = package_search
        self.temporary = tempfile.TemporaryDirectory(prefix="cyberlab-package-cache-test-")
        self.addCleanup(self.temporary.cleanup)
        environment = patch.dict(os.environ, {"XDG_CACHE_HOME": self.temporary.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.directory = self.module.cache_directory()
        self.addCleanup(os.close, self.directory)
        self.entries = {"mousepad": {"id": "mousepad", "name": "mousepad", "description": "Simple text editor", "search": "mousepad simple text editor"}}

    def save(self, age=0):
        from time import time
        document = {"version": self.module.CACHE_VERSION, "architecture": PackageSearch().architecture, "loaded_at": time() - age, "entries": self.entries}
        self.module.write_json(self.directory, "index.json", document, self.module.MAX_CACHE)
        return document

    def test_warm_lookup_never_launches_worker(self):
        self.save()
        with patch.object(self.module, "start_worker") as start:
            result = self.module.search("mouse")
        start.assert_not_called()
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["packages"][0]["id"], "mousepad")

    def test_one_worker_lock_survives_parent_and_blocks_duplicates(self):
        import os
        held = []
        def start(directory, lock):
            held.append(os.dup(lock))
        try:
            with patch.object(self.module, "start_worker", side_effect=start) as spawn:
                self.assertEqual(self.module.search("mouse")["state"], "loading")
                self.assertEqual(self.module.search("editor")["state"], "loading")
                self.assertEqual(spawn.call_count, 1)
        finally:
            for descriptor in held:
                os.close(descriptor)
        self.assertEqual(self.module.search("mouse")["state"], "error")

    def test_failed_refresh_preserves_previous_cache(self):
        import os
        original = self.save(age=7 * 3600)
        lock = os.open("index.lock", os.O_RDWR | os.O_CREAT, 0o600, dir_fd=self.directory)
        def fail(index):
            index.error = "offline"
        with patch.object(self.module.PackageSearch, "_load", fail):
            self.module.update(os.dup(self.directory), lock)
        self.assertEqual(self.module.read_json(self.directory, "index.json", self.module.MAX_CACHE), original)
        result = self.module.search("mouse")
        self.assertTrue(result["cached"])
        self.assertEqual(result["state"], "error")
        self.assertEqual(result["packages"][0]["id"], "mousepad")

    def test_worker_publishes_complete_private_cache(self):
        import os
        lock = os.open("index.lock", os.O_RDWR | os.O_CREAT, 0o600, dir_fd=self.directory)
        def success(index):
            index.entries = self.entries
        with patch.object(self.module.PackageSearch, "_load", success):
            self.module.update(os.dup(self.directory), lock)
        self.assertEqual(self.module.search("mouse")["state"], "ready")
        self.assertEqual(os.stat("index.json", dir_fd=self.directory).st_mode & 0o777, 0o600)
        self.assertEqual(os.listdir(self.directory), [name for name in os.listdir(self.directory) if not name.startswith(".index-")])

    def test_worker_keeps_verified_mozilla_when_optional_refresh_fails(self):
        import os
        document = self.save(age=7 * 3600)
        document["mozilla_entries"] = {"firefox": {"description": "Mozilla Firefox"}}
        self.module.write_json(self.directory, "index.json", document, self.module.MAX_CACHE)
        lock = os.open("index.lock", os.O_RDWR | os.O_CREAT, 0o600, dir_fd=self.directory)
        def partial_success(index):
            index.entries = self.entries
            index.mozilla_error = True
        with patch.object(self.module.PackageSearch, "_load", partial_success):
            self.module.update(os.dup(self.directory), lock)
        with patch.object(self.module, "start_worker") as start:
            result = self.module.search("firefox")
        start.assert_not_called()
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["source_errors"], ["mozilla"])
        self.assertEqual(result["packages"][0]["source"], "mozilla")
        self.assertTrue(result["packages"][0]["application"])

    def test_symlink_cache_and_root_lookup_are_rejected(self):
        import os
        target = Path(self.temporary.name) / "unrelated"
        target.write_text("preserve")
        os.symlink(target, "index.json", dir_fd=self.directory)
        with self.assertRaises(OSError):
            self.module.search("mouse")
        self.assertEqual(target.read_text(), "preserve")
        with patch.object(self.module.os, "geteuid", return_value=0), self.assertRaises(ValueError):
            self.module.cache_directory()

    def test_corrupt_cache_reloads_and_spawn_failure_is_reported(self):
        self.module.write_json(self.directory, "index.json", {"version": 1, "entries": []}, self.module.MAX_CACHE)
        with patch.object(self.module, "start_worker", side_effect=OSError("fixture")):
            result = self.module.search("mouse")
        self.assertEqual(result["state"], "error")
        self.assertFalse(result["cached"])

    def test_empty_query_loads_repository_and_disabled_auto_load_has_no_network(self):
        with patch.object(self.module, "start_worker") as start, patch("cyberlab.authoring.packages.Thread") as thread:
            result = self.module.search("")
            PackageSearch(auto_load=False).search("editor")
        start.assert_called_once()
        thread.assert_not_called()
        self.assertEqual(result["state"], "loading")
        self.assertEqual(result["packages"], [])

    def test_empty_query_browses_real_cached_packages(self):
        self.save()
        with patch.object(self.module, "start_worker") as start:
            result = self.module.search("")
        start.assert_not_called()
        self.assertEqual(result["state"], "ready")
        self.assertEqual([entry["id"] for entry in result["packages"]], ["mousepad"])

    def test_legacy_filtered_cache_is_refreshed(self):
        document = self.save()
        document["version"] = 1
        self.module.write_json(self.directory, "index.json", document, self.module.MAX_CACHE)
        with patch.object(self.module, "start_worker") as start:
            result = self.module.search("firefox")
        start.assert_called_once()
        self.assertEqual(result["state"], "loading")
        self.assertEqual(result["packages"], [])

    def test_cache_keeps_source_identity_and_snap_requirement(self):
        document = self.save()
        document.update(version=2, entries={"firefox": {"description": "Snap browser", "requires_snap": True}},
                        mozilla_entries={"firefox": {"description": "Mozilla browser"}}, mozilla_error=False)
        self.module.write_json(self.directory, "index.json", document, self.module.MAX_CACHE)
        with patch.object(self.module, "start_worker") as start:
            result = self.module.search("firefox")
        start.assert_not_called()
        self.assertEqual([(entry["source"], entry["installable"]) for entry in result["packages"]], [("mozilla", True), ("ubuntu", False)])

    def test_cache_cannot_inject_extra_mozilla_packages(self):
        document = self.save()
        document.update(version=2, mozilla_entries={"curl": {"description": "Fake recipe"}})
        self.module.write_json(self.directory, "index.json", document, self.module.MAX_CACHE)
        with patch.object(self.module, "start_worker"):
            result = self.module.search("curl")
        self.assertEqual(result["packages"], [])


    def test_mozilla_arm64_uses_matching_index(self):
        data = b"Package: firefox\nArchitecture: arm64\nDescription: Firefox browser\n\nPackage: foreign\nArchitecture: amd64\nDescription: Other architecture\n\n"
        release = ("SHA256:\n " + sha256(data).hexdigest() + " " + str(len(data)) + " main/binary-arm64/Packages\n").encode()
        calls = []
        def fetch(url, limit, deadline):
            calls.append(url)
            return release if url.endswith("Release") else data
        index = PackageSearch(fetch=fetch, machine="aarch64", auto_load=False)
        entries = index._load_mozilla(monotonic() + 10)
        self.assertEqual(set(entries), {"firefox"})
        self.assertTrue(calls[-1].endswith("main/binary-arm64/Packages"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
