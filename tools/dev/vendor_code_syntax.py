"""Rebuild the QML-only highlight.js bundle from its pinned npm archive."""

import argparse
import base64
import hashlib
import re
from pathlib import Path
import tarfile


INTEGRITY = "Xwwo44whKBVCYoliBQwaPvtd/2tYFkRQtXDWj1nackaV2JPXx3L0+Jvd8/qCJ2p+ML0/XVkJ2q+Mr+UVdpJK5w=="
LANGUAGES = ("python", "bash", "json", "yaml", "javascript", "markdown")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="highlight.js-11.11.1.tgz from registry.npmjs.org")
    arguments = parser.parse_args()
    digest = base64.b64encode(hashlib.sha512(arguments.archive.read_bytes()).digest()).decode()
    if digest != INTEGRITY:
        raise SystemExit("Archive does not match highlight.js 11.11.1")
    target = Path(__file__).resolve().parents[2] / "ui/studio/vendor"
    target.mkdir(exist_ok=True)
    with tarfile.open(arguments.archive) as archive:
        def read(name):
            return archive.extractfile("package/" + name).read().decode()

        bundle = "export var engine = (function() {\nvar module = {exports: {}};\n"
        core = read("lib/core.js")
        core = core.replace("function deepFreeze(obj) {", "function deepFreeze(obj) {\n  if (obj === null || obj === undefined) return obj;")
        guard = "if ((type === 'object' || type === 'function') && !Object.isFrozen(prop))"
        assert core.count(guard) == 1
        core = core.replace(guard, "if (prop !== null && (type === 'object' || type === 'function') && !Object.isFrozen(prop))")
        anchor = "  function _highlight(languageName, codeToHighlight, ignoreIllegals, continuation) {"
        locals = ("language", "top", "continuations", "emitter", "modeBuffer", "relevance", "index", "iterations", "resumeScanAtSamePosition")
        start = core.index(anchor)
        prefix, highlight = core[:start], core[start:]
        for name in locals:
            highlight, count = re.subn(r"^    (?:const|let) " + name + r" =", "    " + name + " =", highlight, count=1, flags=re.MULTILINE)
            assert count == 1, name
        core = prefix + highlight.replace(anchor, anchor + "\n    let " + ", ".join(locals) + ";", 1)
        bundle += core + "\nreturn module.exports;\n})();\n"
        for language in LANGUAGES:
            bundle += 'engine.registerLanguage("' + language + '", (function() {\nvar module = {exports: {}};\n'
            grammar = read("lib/languages/" + language + ".js")
            if language == "python":
                grammar = grammar.replace(r"/[\p{XID_Start}_]\p{XID_Continue}*/u", r"/[A-Za-z_\u0080-\uFFFF][\w\u0080-\uFFFF]*/")
                grammar = grammar.replace("unicodeRegex: true", "unicodeRegex: false")
            bundle += grammar + "\nreturn module.exports;\n})());\n"
        (target / "Highlight.mjs").write_text(bundle)
        (target / "highlightjs.LICENSE.txt").write_text(read("LICENSE"))
    print("Vendored highlight.js 11.11.1: " + ", ".join(LANGUAGES))


if __name__ == "__main__":
    main()
