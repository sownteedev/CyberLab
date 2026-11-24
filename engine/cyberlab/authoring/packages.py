from hashlib import sha256
import lzma
import logging
import platform
import re
from threading import Lock, Thread
from time import monotonic
import unicodedata
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener

from cyberlab.lab.software import PACKAGE_NAME

MAX_COMPRESSED = 32 * 1024**2
MAX_EXPANDED = 160 * 1024**2
MAX_PACKAGES = 180000
MOZILLA_BASE = "https://packages.mozilla.org/apt/dists/mozilla/"
SEARCH_ALIASES = {"trinh duyet": "web browser", "soan thao": "text editor", "bat goi": "packet capture", "quet cong": "port scan", "may chu web": "web server", "co so du lieu": "database", "giai nen": "archive"}


def normalized(value):
    return "".join(character for character in unicodedata.normalize("NFD", value.lower().replace("đ", "d")) if not unicodedata.combining(character))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        raise ValueError("Package index redirects are not accepted")


def download(url, limit, deadline):
    opener = build_opener(ProxyHandler({}), HTTPSHandler(), NoRedirect())
    request = Request(url, headers={"User-Agent": "CyberLab-PackageSearch/1"})
    with opener.open(request, timeout=15) as response:
        data = bytearray()
        while True:
            if monotonic() >= deadline:
                raise TimeoutError("Package index download timed out")
            chunk = response.read(min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError("Package index exceeds download limit")
        return bytes(data)


def release_entries(data):
    entries = {}
    section = False
    for line in data.decode("utf-8").splitlines():
        if line == "SHA256:":
            section = True
        elif section and line.startswith(" "):
            digest, size, path = line.split()
            if re.fullmatch(r"[0-9a-f]{64}", digest):
                entries[path] = (digest, int(size))
        elif section:
            break
    return entries


def package_lines(data, deadline):
    decoder = lzma.LZMADecompressor(memlimit=128 * 1024**2)
    pending = b""
    expanded = 0
    chunk = data
    while True:
        output = decoder.decompress(chunk, max_length=65536)
        chunk = b""
        expanded += len(output)
        if expanded > MAX_EXPANDED or monotonic() >= deadline:
            raise ValueError("Package index exceeds parsing limits")
        pending += output
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            if len(line) > 1024**2:
                raise ValueError("Package index line is too large")
            yield line
        if len(pending) > 1024**2:
            raise ValueError("Package index line is too large")
        if decoder.eof:
            remaining = decoder.unused_data.lstrip(b"\x00")
            if (len(decoder.unused_data) - len(remaining)) % 4:
                raise ValueError("Invalid XZ padding")
            if remaining:
                decoder = lzma.LZMADecompressor(memlimit=128 * 1024**2)
                chunk = remaining
                continue
            if pending:
                yield pending
            yield b""
            return
        if decoder.needs_input:
            raise ValueError("Truncated package index")


def parse_packages(data, architecture, deadline):
    return parse_package_records(package_lines(data, deadline), architecture)

def parse_package_records(lines, architecture):
    entries = {}
    fields = {}
    for line in lines:
        if not line.strip():
            name = fields.get("Package", "")
            if PACKAGE_NAME.fullmatch(name) and fields.get("Architecture") in {architecture, "all"}:
                description = fields.get("Description", "")[:240]
                entry = {"id": name, "name": name, "description": description}
                dependencies = fields.get("Depends", "") + "," + fields.get("Pre-Depends", "")
                if ("transitional" in description.lower() and re.search(r"\bsnap\b", description.lower())) or re.search(r"(?:^|[,|])\s*snapd(?:[:\s(]|$)", dependencies):
                    entry["requires_snap"] = True
                entries[name] = entry
                if len(entries) > MAX_PACKAGES:
                    raise ValueError("Too many packages in index")
            fields = {}
        elif not line.startswith(b" "):
            key, separator, value = line.decode("utf-8", "replace").partition(": ")
            if separator and key in {"Package", "Architecture", "Description", "Depends", "Pre-Depends"}:
                fields[key] = value.strip()
    return entries

def package_choice(entry, source):
    package = {key: value for key, value in entry.items() if key not in {"search", "keywords"}}
    package["source"] = source
    reason = ""
    if source == "ubuntu":
        if entry.get("requires_snap") or entry["id"] in {"firefox", "snapd", "chromium-browser"}:
            reason = "snap"
        elif entry["id"] in {"tshark", "wireshark-common"}:
            reason = "wireshark"
    package["installable"] = not reason
    package["unavailable_reason"] = reason
    if (source == "mozilla" and entry["id"] == "firefox") or (source == "ubuntu" and entry["id"] == "wireshark"):
        package["application"] = True
    return package


class PackageSearch:
    def __init__(self, fetch=download, machine=None, clock=monotonic, auto_load=True):
        self.fetch = fetch
        self.auto_load = auto_load
        self.clock = clock
        self.architecture = {"x86_64": "amd64", "aarch64": "arm64"}.get(machine or platform.machine())
        self.lock = Lock()
        self.entries = {}
        self.mozilla_entries = {}
        self.mozilla_error = False
        self.loading = False
        self.loaded_at = None
        self.attempted_at = None
        self.error = ""

    def _load_mozilla(self, deadline):
        path = "main/binary-" + self.architecture + "/Packages"
        release = release_entries(self.fetch(MOZILLA_BASE + "Release", 2 * 1024**2, deadline))
        digest, size = release[path]
        if not 0 < size <= 2 * 1024**2:
            raise ValueError("Invalid Mozilla index size")
        data = self.fetch(MOZILLA_BASE + path, size, deadline)
        if len(data) != size or sha256(data).hexdigest() != digest:
            raise ValueError("Mozilla package index checksum mismatch")
        entries = parse_package_records(data.splitlines() + [b""], self.architecture)
        return {name: entry for name, entry in entries.items() if name == "firefox" and not entry.get("requires_snap")}

    def _load(self):
        try:
            entries = {}
            deadline = monotonic() + 180
            for suite in ("noble", "noble-updates", "noble-security"):
                host = "https://ports.ubuntu.com/ubuntu-ports" if self.architecture == "arm64" else ("https://security.ubuntu.com/ubuntu" if suite.endswith("security") else "https://archive.ubuntu.com/ubuntu")
                base = host + "/dists/" + suite + "/"
                release = release_entries(self.fetch(base + "Release", 2 * 1024**2, deadline))
                for component in ("main", "universe", "restricted", "multiverse"):
                    path = component + "/binary-" + self.architecture + "/Packages.xz"
                    digest, size = release[path]
                    if not 0 < size <= MAX_COMPRESSED:
                        raise ValueError("Invalid package index size")
                    url = base + path.rsplit("/", 1)[0] + "/by-hash/SHA256/" + digest
                    data = self.fetch(url, size, deadline)
                    if len(data) != size or sha256(data).hexdigest() != digest:
                        raise ValueError("Package index checksum mismatch")
                    entries.update(parse_packages(data, self.architecture, deadline))
                    if len(entries) > MAX_PACKAGES:
                        raise ValueError("Too many packages in catalog")
            for entry in entries.values():
                entry["search"] = normalized(entry["name"] + " " + entry["description"])
            try:
                mozilla_entries = self._load_mozilla(deadline)
                mozilla_error = False
            except Exception as error:
                logging.getLogger(__name__).warning("Mozilla package index unavailable: %s", error)
                mozilla_entries = self.mozilla_entries
                mozilla_error = True
            with self.lock:
                self.entries = entries
                self.mozilla_entries = mozilla_entries
                self.mozilla_error = mozilla_error
                self.loaded_at = self.clock()
                self.error = ""
        except Exception as error:
            logging.getLogger(__name__).warning("Ubuntu package index unavailable: %s", error)
            with self.lock:
                self.error = "unavailable"
        finally:
            with self.lock:
                self.loading = False

    def search(self, query, refresh=False):
        if not isinstance(query, str) or len(query) > 100 or any(ord(character) < 32 for character in query):
            raise ValueError("Search must contain at most 100 printable characters")
        if type(refresh) is not bool:
            raise ValueError("Invalid search refresh option")
        query_text = normalized(query.strip())
        translated = query_text
        for phrase, replacement in SEARCH_ALIASES.items():
            translated = translated.replace(phrase, replacement)
        terms = query_text.split()
        alternative = translated.split()
        with self.lock:
            now = self.clock()
            stale = self.loaded_at is None or now - self.loaded_at >= 6 * 3600
            retry = self.attempted_at is None or now - self.attempted_at >= (10 if refresh else 60)
            if self.auto_load and self.architecture and not self.loading and (stale or refresh) and retry:
                self.loading = True
                self.attempted_at = now
                self.error = ""
                Thread(target=self._load, daemon=True, name="ubuntu-package-index").start()
            entries = self.entries
            mozilla_entries = self.mozilla_entries
            source_errors = ["mozilla"] if self.mozilla_error else []
            state = "loading" if self.loading else "error" if self.error or not self.architecture else "ready" if self.loaded_at is not None else "idle"
        matches = []
        for source, catalog in (("ubuntu", entries), ("mozilla", mozilla_entries)):
            for entry in catalog.values():
                search = entry.get("search") or normalized(entry["name"] + " " + entry.get("description", "") + " " + entry.get("keywords", "") + " " + entry["id"])
                if not terms or all(term in search for term in terms) or all(term in search for term in alternative):
                    matches.append(package_choice(entry, source))
        text = normalized(query.strip())
        if text:
            matches.sort(key=lambda entry: (entry["id"] != text, not entry["id"].startswith(text), not all(term in entry["id"] for term in terms), entry["id"].startswith("lib") or entry["id"].endswith(("-dev", "-doc", "-data", "-common", "-dbg", "-dbgsym")), len(entry["id"]), entry["id"], not entry["installable"]))
        else:
            matches.sort(key=lambda entry: (entry["id"], not entry["installable"]))
        return {"state": state, "cached": bool(entries), "total": len(matches), "distribution": "Ubuntu 24.04", "architecture": self.architecture or "unsupported", "packages": matches[:40], "source_errors": source_errors}
