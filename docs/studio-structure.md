# Studio source organization

The 2026-10-23 reorganization separates the existing desktop UI by responsibility.
It does not replace the design or change the CLI, System D-Bus API, daemon,
Engine, Docker policy, Quickshell/Qt runtime, or persistent catalog.

```text
ui/
  launcher.py                Installed, unprivileged desktop entry point
  studio/
    shell.qml                Bootstrap: wire services, window and polling
    qmldir                   One registry of public QML types
    app/                     AppBar, rail, window, routes and confirmations
    components/              Shared buttons, inputs, cards, tree and Markdown
    services/                CLI transport, workflows and local preferences
    models/                  Pure JavaScript transformations and layout helpers
    theme/                   Shared color, typography, spacing and motion tokens
    views/
      library/               Lab library and documentation detail
      practice/              Sessions, nodes, workspace file dialogs
      editor/                Draft forms, resources, review and confirmations
      settings/              Appearance settings dialog and controls
    assets/icons/            Bundled SVG icons, license and source information
    testing/                 Isolated UI smoke orchestration
```

## Boundaries

- `Backend.qml` is the only QML process runner. It calls the unprivileged CLI
  with explicit argv and retains serialized requests, read-only loading and
  mutation locks. Neither views nor services gain Docker access.
- `StudioState.qml` coordinates catalog, Session and workspace state. It receives
  the transport through its `api` property.
- `DraftService.qml` owns draft editing, revision/digest guards, save, upload,
  validation and publication. It is a nonvisual `QtObject` with injected
  `backend`; review requests are signals, not references to dialogs.
- `DraftEditor.qml` composes that service with forms and confirmation dialogs.
  Its `service` property exposes the editor state to application navigation.
- `StudioWindow.qml` handles window bounds, settings and guarded navigation;
  `StudioContent.qml` wires screens; `StudioDialogs.qml` owns destructive-action
  confirmations. Closing or navigating away still protects unsaved edits.
- `AppearanceStore.qml` persists only local appearance preferences. `Theme.qml`
  remains the single source of visual tokens, including compact typography,
  stable button sizing and reduced motion.

## QML imports and packaging

This is one QML directory module, not a separate module for each folder.
`qmldir` maps stable type names to their nested files. Components import the
module root relatively; the `Studio` qualifier accesses the same `Theme`
singleton everywhere. JavaScript and icon URLs are relative to their files.
Do not add duplicate Theme registrations or flat compatibility copies.

The wheel includes nested QML, JavaScript and local SVG resources through
`pyproject.toml`. A clean build must not reuse a previous `build/lib` tree,
which could retain removed flat resources. The installed launcher still opens
`cyberlab_studio/studio/shell.qml`, so desktop shortcuts do not change.

## Verification and deployment

UI tests copy the complete module tree into temporary directories. Structural
checks verify the registry, package-data coverage and service boundaries;
offscreen checks exercise navigation, dirty-draft protection, mutation callbacks,
themes, layouts and the private MemoryRuntime workflow. Test process groups are
cleaned up; user preferences and the production catalog are not test fixtures.

Build the wheel into an isolated build directory, verify its actual resource
inventory and run the installed wheel against a private test-session D-Bus.
Deploy only with `tools/upgrade_runtime.py`, its checksum and retained backup,
after every allowed user's Sessions are STOPPED. Preserve any unsaved main
Studio editor before relaunching. Final visual acceptance remains manual.
