# Maintained Tools

The normal entry point is `bash install.sh` at the repository root.

| File | Purpose |
| --- | --- |
| `install/packages.sh` | Native package-manager adapters for Arch, Debian/Ubuntu, Fedora and openSUSE. |
| `install/docker.sh` | Detect and preserve the existing system Docker provider; reject conflicting/shim/custom setups. |
| `install/repositories.sh` | Explicit opt-in native Quickshell sources with pinned signing-key fingerprints; never overwrite another repository configuration. |
| `install/transactions.sh` | Resolve/review dependency changes, require upgrade approval and retain transaction receipts. |
| `install/apt-transaction-guard.sh` | Reject unreviewed .deb versions immediately before dpkg installs them. |
| `install/probe.qml` | Offscreen native Qt/QML and SVG icon-decoding probe, also used by `--check`; no catalog access. |
| `runtime_admin.py` | Safe account/path checks, unprivileged builds, configuration generation and installation verification. |
| `upgrade_runtime.py` | All-users Session guard, private backup/rollback and runtime update. |
| `run_studio.sh` | Launch the source UI using the local editable venv; never sudo. |
| `run_studio.py` | Small compatibility entry point for existing desktop shortcuts. |
| `check_labs.py` | Validate an explicitly supplied catalog without installing it. |
| `prepare_lab_images.py` | Explicit administrator workflow for bounded, reviewed image recipes. |

Python remains the implementation language of the application and of the
security-sensitive helpers. Package installation, venv installation, service
registration and the normal deployment sequence are orchestrated by Bash.
Do not replace structured manifest checks or backup/rollback with unchecked
shell text processing just to remove `.py` files.

The obsolete MVP, OVA, AppImage-download, migration and fixture-preview scripts
were moved outside this checkout to the local user's
`~/.local/state/cyberlab/development-archives/` directory. They are not required
on a new machine. Historical documents mentioning them are not current setup
instructions; use `docs/install-mvp.md` and the root README instead.
