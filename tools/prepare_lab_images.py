"""Package reviewed Lab image recipes and build them explicitly as administrator."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import tempfile

MAX_CONTEXT_BYTES = 32 * 1024 * 1024
MAX_CONTEXT_ENTRIES = 512
MAX_BUNDLE_BYTES = 128 * 1024 * 1024
DOCKER = ("/usr/bin/docker", "--host", "unix:///var/run/docker.sock")
ENVIRONMENT = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root", "LANG": "C.UTF-8"}
IMAGE = re.compile(r"[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\Z")


def safe_path(value):
    return isinstance(value, str) and len(value) <= 240 and 1 <= len(value.split("/")) <= 12 and all(
        re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", part) for part in value.split("/"))


def read_file(path, limit):
    path = Path(path)
    if any(parent.is_symlink() for parent in path.absolute().parents):
        raise ValueError("Input ancestors cannot be symlinks")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise ValueError("Expected a bounded regular file, not a link")
        content = source.read(limit + 1)
        after = os.fstat(source.fileno())
    if len(content) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("Input changed while reading")
    return content


def inspect_recipe(data):
    text = data.decode("utf-8")
    if len(data) > 65536 or "\0" in text or "<<" in text:
        raise ValueError("Recipe too large or uses unsupported heredoc syntax")
    instructions = []
    pending = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            if re.match(r"#\s*(syntax|escape|check)\s*=", line, re.IGNORECASE):
                raise ValueError("Dockerfile frontend/parser directives are not supported")
            continue
        if not line:
            continue
        pending += line[:-1] + " " if line.endswith("\\") else line
        if line.endswith("\\"):
            continue
        instruction, separator, value = pending.partition(" ")
        instruction, value = instruction.upper(), value.strip()
        if not separator or not value:
            raise ValueError("Invalid Dockerfile instruction")
        instructions.append((instruction, value))
        pending = ""
    if pending or not instructions or instructions[0][0] != "FROM":
        raise ValueError("Recipe must start with a single explicit FROM")
    base = instructions[0][1]
    if not IMAGE.fullmatch(base) or base.rsplit(":", 1)[1] == "latest":
        raise ValueError("Base image requires an explicit local tag, not latest, ARG or a remote context")
    for instruction, value in instructions[1:]:
        if instruction not in {"RUN", "COPY", "USER", "WORKDIR", "ENV", "CMD", "LABEL", "EXPOSE"}:
            raise ValueError(f"Unsupported recipe instruction: {instruction}")
        if instruction == "RUN" and value.startswith("--"):
            raise ValueError("RUN flags, mounts and entitlements are not supported")
        if instruction == "COPY":
            arguments = json.loads(value) if value.startswith("[") else value.split()
            if arguments != ["rootfs/", "/"]:
                raise ValueError("COPY must copy only rootfs/ to /; no external stages or contexts")
    return base


def pack_context(root):
    root = Path(root)
    for ancestor in (*reversed(root.absolute().parents), root.absolute()):
        if ancestor.is_symlink():
            raise ValueError("Recipe directory ancestors cannot be symlinks")
    buffer = BytesIO()
    size = 0
    count = 0
    recipe = None
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for directory, directories, names in os.walk(root, followlinks=False):
            directories.sort()
            names.sort()
            for name in directories + names:
                path = Path(directory) / name
                relative = path.relative_to(root).as_posix()
                status = path.lstat()
                if not safe_path(relative) or relative != "Dockerfile" and not (relative == "rootfs" or relative.startswith("rootfs/")):
                    raise ValueError("Context accepts only Dockerfile and rootfs/ with safe relative paths")
                if status.st_dev != root.stat().st_dev or not (stat.S_ISREG(status.st_mode) or stat.S_ISDIR(status.st_mode)):
                    raise ValueError("Context cannot contain links, special files or filesystem crossings")
                count += 1
                if count > MAX_CONTEXT_ENTRIES:
                    raise ValueError("Recipe context has too many entries")
                data = None if stat.S_ISDIR(status.st_mode) else read_file(path, MAX_CONTEXT_BYTES - size)
                if data is not None:
                    size += len(data)
                info = tarfile.TarInfo(relative)
                info.type = tarfile.DIRTYPE if data is None else tarfile.REGTYPE
                info.mode = 0o755 if data is None or status.st_mode & 0o111 else 0o644
                info.size = 0 if data is None else len(data)
                archive.addfile(info, None if data is None else BytesIO(data))
                if relative == "Dockerfile":
                    recipe = data
    if recipe is None:
        raise ValueError("Recipe is missing Dockerfile")
    return buffer.getvalue(), inspect_recipe(recipe)


def plan(lab_directory, output):
    if os.geteuid() == 0:
        raise ValueError("Prepare and review recipes as the developer user, not root")
    from cyberlab.lab import LabError, load_lab

    lab_directory = lab_directory.absolute()
    output = output.absolute()
    if output.is_symlink():
        raise ValueError("Output directory cannot be a symlink")
    output = output.resolve()
    if output.exists() or output.is_symlink() or lab_directory.resolve() in output.parents or "CyberLab-labs" in output.parts:
        raise ValueError("Choose a new output directory outside the persistent catalog and Lab source")
    try:
        lab = load_lab(lab_directory / "lab.yaml")
    except LabError as error:
        raise ValueError(f"Invalid Lab source: {error}") from None
    nodes = []
    contexts = {}
    references = {}
    for node in lab.nodes:
        if node.image is None or not IMAGE.fullmatch(node.image) or node.image.rsplit(":", 1)[1] == "latest":
            raise ValueError("Each node requires an explicit versioned image tag")
        entry = {"node": node.id, "image": node.image, "context": None}
        recipe = lab_directory / "image-source" / node.id
        if recipe.exists() or recipe.is_symlink():
            content, base = pack_context(recipe)
            if base == node.image:
                raise ValueError("Output image tag must differ from the base tag")
            filename = f"{node.id}.tar"
            contexts[filename] = content
            entry.update(context=filename, sha256=sha256(content).hexdigest(), base=base)
            previous = references.setdefault(node.image, entry["sha256"])
            if previous != entry["sha256"]:
                raise ValueError("Nodes sharing an image cannot supply different recipes")
        nodes.append(entry)
    if sum(map(len, contexts.values())) > MAX_BUNDLE_BYTES:
        raise ValueError("Image preparation bundle exceeds size limit")
    manifest = {"format": 1, "lab_id": lab.metadata.id, "lab_version": lab.metadata.version, "nodes": nodes}
    validate_manifest(manifest)
    data = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name, content in contexts.items():
        (output / name).write_bytes(content)
    (output / "manifest.json").write_bytes(data)
    print(f"Prepared {len(contexts)} recipe contexts; no Docker action or catalog write.")
    print(f"Manifest SHA-256: {sha256(data).hexdigest()}")
    print("Review manifest and all Dockerfile/rootfs contents before administrator build.")


def docker(*arguments):
    return subprocess.run([*DOCKER, *arguments], env=ENVIRONMENT, check=True, capture_output=True,
                          text=True, timeout=900).stdout


def inspect_image(reference):
    result = json.loads(docker("image", "inspect", reference))[0]
    configuration = result.get("Config") or {}
    if configuration.get("Volumes") or configuration.get("OnBuild"):
        raise ValueError("Images with declared volumes or inherited ONBUILD instructions are not supported")
    identifier = result.get("Id", "")
    if re.fullmatch(r"sha256:[a-f0-9]{64}", identifier) is None:
        raise ValueError("Docker returned an invalid image identity")
    return identifier


def unpack_context(data, destination):
    total = 0
    paths = set()
    with tarfile.open(fileobj=BytesIO(data), mode="r:") as archive:
        for entry in archive:
            if not safe_path(entry.name) or entry.name in paths or not (entry.isfile() or entry.isdir()):
                raise ValueError("Unsafe or duplicate image context member")
            if entry.name != "Dockerfile" and not (entry.name == "rootfs" or entry.name.startswith("rootfs/")):
                raise ValueError("Unexpected context member")
            paths.add(entry.name)
            total += entry.size
            if len(paths) > MAX_CONTEXT_ENTRIES or total > MAX_CONTEXT_BYTES:
                raise ValueError("Unpacked context exceeds limits")
            target = destination / entry.name
            if entry.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o700)
                target.chmod(0o755)
            else:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                stream = archive.extractfile(entry)
                with target.open("xb") as output:
                    output.write(stream.read(MAX_CONTEXT_BYTES + 1))
                target.chmod(0o755 if entry.mode & 0o111 else 0o644)
    for directory, directories, names in os.walk(destination):
        for name in directories:
            (Path(directory) / name).chmod(0o755)
    return inspect_recipe(read_file(destination / "Dockerfile", 65536))


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {"format", "lab_id", "lab_version", "nodes"} or type(manifest["format"]) is not int or manifest["format"] != 1:
        raise ValueError("Unsupported image manifest")
    if not isinstance(manifest["lab_id"], str) or re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", manifest["lab_id"]) is None or len(manifest["lab_id"]) > 64:
        raise ValueError("Invalid manifest Lab identity")
    if not isinstance(manifest["lab_version"], str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", manifest["lab_version"]) is None:
        raise ValueError("Invalid manifest Lab version")
    nodes = manifest["nodes"]
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 4:
        raise ValueError("Expected one to four image nodes")
    identities = set()
    outputs = {}
    for entry in nodes:
        if not isinstance(entry, dict):
            raise ValueError("Invalid image node")
        context = entry.get("context")
        expected_keys = {"node", "image", "context"} | ({"sha256", "base"} if context is not None else set())
        if set(entry) != expected_keys:
            raise ValueError("Unexpected image manifest fields")
        node = entry["node"]
        if not isinstance(node, str) or re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", node) is None or len(node) > 64 or node in identities:
            raise ValueError("Invalid or duplicate image node")
        identities.add(node)
        image = entry["image"]
        if not isinstance(image, str) or not IMAGE.fullmatch(image) or image.rsplit(":", 1)[1] == "latest":
            raise ValueError("Invalid output image tag")
        if context is not None:
            if context != node + ".tar" or not isinstance(entry["sha256"], str) or re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]) is None:
                raise ValueError("Invalid recipe context or digest")
            if not isinstance(entry["base"], str) or not IMAGE.fullmatch(entry["base"]):
                raise ValueError("Invalid base image")
            previous = outputs.setdefault(image, entry["sha256"])
            if previous != entry["sha256"]:
                raise ValueError("Conflicting recipes for the same output tag")
    return outputs


def build(bundle, expected):
    if os.geteuid() != 0:
        raise ValueError("Only administrator may build reviewed images; never add the learner to the Docker group")
    if re.fullmatch(r"[a-f0-9]{64}", expected) is None:
        raise ValueError("Provide the reviewed manifest SHA-256")
    manifest_bytes = read_file(bundle / "manifest.json", 65536)
    if sha256(manifest_bytes).hexdigest() != expected:
        raise ValueError("Manifest changed since review")
    manifest = json.loads(manifest_bytes)
    outputs = validate_manifest(manifest)
    for image in outputs:
        if docker("image", "ls", "--quiet", "--filter", f"reference={image}").strip():
            raise ValueError("Output image already exists; choose a new version tag, never overwrite a released image")
    stage = Path(tempfile.mkdtemp(prefix="cyberlab-image-build-", dir="/var/tmp"))
    print(f"Administrator staging retained at {stage}", flush=True)
    (stage / "manifest.json").write_bytes(manifest_bytes)
    prepared = []
    context_bytes = 0
    for index, entry in enumerate(manifest["nodes"]):
        image = entry.get("image", "")
        if not isinstance(image, str) or not IMAGE.fullmatch(image) or image.rsplit(":", 1)[1] == "latest":
            raise ValueError("Invalid output image tag")
        if entry.get("context") is None:
            prepared.append((entry, None, None if image in outputs else inspect_image(image)))
            continue
        filename = entry["context"]
        if not isinstance(filename, str) or re.fullmatch(r"[a-z][a-z0-9-]{0,63}\.tar", filename) is None:
            raise ValueError("Invalid context filename")
        data = read_file(bundle / filename, MAX_CONTEXT_BYTES + 2 * 1024 * 1024)
        context_bytes += len(data)
        if context_bytes > MAX_BUNDLE_BYTES:
            raise ValueError("Image preparation bundle exceeds size limit")
        if sha256(data).hexdigest() != entry.get("sha256"):
            raise ValueError("Recipe context changed since review")
        directory = stage / f"node-{index}"
        directory.mkdir(mode=0o700)
        base = unpack_context(data, directory)
        if base != entry.get("base") or base == image:
            raise ValueError("Base image differs from reviewed manifest")
        prepared.append((entry, directory, inspect_image(base)))
    inventory = []
    built = {}
    for entry, directory, identifier in prepared:
        image = entry["image"]
        if directory is not None:
            fingerprint = entry["sha256"]
            if image in built and built[image][0] != fingerprint:
                raise ValueError("Conflicting recipes for the same output tag")
            if image not in built:
                existing = docker("image", "ls", "--quiet", "--filter", f"reference={image}").strip()
                if existing:
                    raise ValueError("Output image already exists; choose a new version tag, never overwrite a released image")
                if inspect_image(entry["base"]) != identifier:
                    raise ValueError("Local base image changed during preparation")
                log_path = stage / f"build-{entry['node']}.log"
                try:
                    output = docker("build", "--builder", "default", "--load", "--pull=false", "--network=none",
                                    "--label", f"org.ptit.cyberlab.recipe={fingerprint}", "--tag", image, str(directory))
                except subprocess.CalledProcessError as error:
                    log_path.write_text((error.stdout or "") + (error.stderr or ""))
                    raise ValueError(f"Image build failed; inspect {log_path}") from None
                log_path.write_text(output)
                built[image] = (fingerprint, inspect_image(image))
            identifier = built[image][1]
        inventory.append({"node": entry["node"], "image": image, "image_id": identifier})
    for entry in inventory:
        if entry["image_id"] is None:
            entry["image_id"] = built[entry["image"]][1]
    (stage / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    print(json.dumps(inventory, indent=2))
    print("Images are local. Daemon allowlist is unchanged; administrator approval is a separate step.")
    print("No Lab was started. Recipe builds do not prove runtime account or service compatibility.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    prepare = actions.add_parser("plan", help="Snapshot recipes as a normal user; no Docker access")
    prepare.add_argument("lab", type=Path)
    prepare.add_argument("output", type=Path)
    execute = actions.add_parser("build", help="Explicit administrator build of a reviewed bundle")
    execute.add_argument("bundle", type=Path)
    execute.add_argument("--reviewed-sha256", required=True)
    arguments = parser.parse_args()
    try:
        if arguments.action == "plan":
            plan(arguments.lab, arguments.output)
        else:
            build(arguments.bundle, arguments.reviewed_sha256)
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Image preparation failed: {error}. Preserve any staging directory; do not blindly retry.")


if __name__ == "__main__":
    main()
