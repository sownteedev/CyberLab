# Project-local Qt skills

Installed on 2026-10-16 for CyberLab development only.

Source: `TheQtCompanyRnD/agent-skills` on GitHub.
Pinned commit: `a784c48445e34f126760f17ba0600a25f2d19968`.

| Local skill | Upstream directory | Purpose |
| --- | --- | --- |
| `skills/qt-qml` | `skills/qt-qml` | QML implementation, bindings and component structure |
| `skills/qt-qml-review` | `skills/qt-qml-review` | Read-only QML review and lint guidance |
| `skills/qt-ui-design` | `skills/qt-ui-design` | Layout, navigation, interaction and visual design |
| `skills/material-3` | `hamen/material-3-skill/skills/material-3` | Material 3 tokens, components, layout and accessibility guidance |

The skill directories are unmodified upstream copies, including their bundled
references, helper script and LICENSE.txt files. Use the skills from this project;
no user-global skill installation or runtime dependency was added.

The Qt skills are pinned to commit
`a784c48445e34f126760f17ba0600a25f2d19968`.

Material 3 is pinned to commit
`14385f2bf3804d8779f8b4db2604211f1e70b4c1` and is MIT licensed by its upstream
project. Invoke explicitly with `$qt-qml`, `$qt-qml-review`, `$qt-ui-design` or
`$material-3` in a request.
These are coding-assistant instructions, not Quickshell plugins or application
features. Installing them does not redesign the UI, install a Material runtime
library, or execute a bundled linter.

Material 3 is primarily written for Jetpack Compose, Flutter and web. For
CyberLab it is a design reference: translate its tokens and interaction rules
into the existing Quickshell/QML components; do not add Compose, Flutter, web
components or a new transport.

CyberLab's root AGENTS.md and explicit user approvals still govern all work.
Keep Studio on Quickshell and the existing System D-Bus API. Do not treat skill
suggestions as permission to change the architecture, install MCP servers or
upgrade Qt. Check the installed Qt/Quickshell versions before applying examples.
Do not use the persistent CyberLab-labs catalog for previews or smoke tests.
