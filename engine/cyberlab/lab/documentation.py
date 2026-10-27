from dataclasses import replace

from .assets import AssetError, snapshot_lab, valid_path
from .models import Documentation, FileMapping, Node

MAX_DOCUMENT_BYTES = 64 * 1024

def validate_documentation(documentation, loaded=False):
    if documentation is None:
        return
    source = documentation.source
    if not valid_path(source) or not source.startswith("assets/") or not source.endswith(".md"):
        raise AssetError("Documentation must be a safe assets-relative Markdown file")
    if loaded and documentation.content is None:
        raise AssetError("Documentation must be loaded from the Lab package")
    if documentation.content is not None and (
        not isinstance(documentation.content, str)
        or "\x00" in documentation.content
        or len(documentation.content.encode("utf-8")) > MAX_DOCUMENT_BYTES
    ):
        raise AssetError("Documentation must be text without NUL bytes and at most 64 KiB")

def snapshot_documentation(lab, project):
    if lab.documentation is None:
        return lab
    validate_documentation(lab.documentation)
    node = Node("documentation", (), files=(FileMapping(lab.documentation.source, "manual.md"),))
    snapshot = snapshot_lab(replace(lab, nodes=(node,)), project).nodes[0].seed
    if len(snapshot) != 1 or snapshot[0].data is None or len(snapshot[0].data) > MAX_DOCUMENT_BYTES:
        raise AssetError("Documentation must be one regular file of at most 64 KiB")
    try:
        content = snapshot[0].data.decode("utf-8")
    except UnicodeError:
        raise AssetError("Documentation must be UTF-8 Markdown") from None
    documentation = Documentation(lab.documentation.source, content)
    validate_documentation(documentation, loaded=True)
    return replace(lab, documentation=documentation)
