# CyberLab Visual Identity

The original CyberLab app icon combines a laboratory flask, a protective shield
silhouette and a terminal prompt. Mint/turquoise on a midnight-blue tile keeps
the mark visible on both light and dark desktops; the amber dot is a lab bubble.
There are no letters, embedded fonts, raster images or external resources.

Source: `ui/studio/assets/branding/cyberlab-studio.svg` (512-unit SVG). This is
CyberLab-specific artwork, separate from the third-party Material UI symbols.
Use it in full color, without the monochrome `Icon` component's tinting. Studio
uses the same SVG in its navigation rail and checks image loading in UI smoke.

The wheel contains both the QML resource and a data-file copy installed at
`share/cyberlab/cyberlab-studio.svg` under the Python environment. The standard
desktop entry uses `/usr/lib/cyberlab/venv/share/cyberlab/cyberlab-studio.svg`,
which is stable across Python versions and independent of the host icon theme.
The existing venv backup/rollback also covers the icon; no new service or theme
package is needed. Fresh installations use this entry. The guarded runtime
updater preserves existing desktop shortcuts, including personal overrides.

For an existing installation, a same-name user desktop entry can use an
absolute path to the icon deployed under the user's XDG data
`icons/hicolor/scalable/apps` directory, without relying on theme lookup.
This changes launcher/Dock artwork without replacing the runtime or touching
Sessions. The installed in-app navigation mark changes after a normal guarded
runtime update and reopening Studio with editor work saved.

## Verification (2026-10-28)

- Rendered and visually checked the SVG at small sizes on light/dark surfaces.
- Qt 6 qmllint completed without errors; existing unrelated warnings remain.
- Offscreen Studio smoke passed from source and installed wheel QML, including
  the bundled image readiness assertion. Both used a private D-Bus session,
  memory-test runtime and temporary catalog/configuration, not user data.
- Installation into a temporary venv confirmed identical QML-resource and
  shared SVG copies. The existing guarded wheel validator accepted the artifact.
- The personal desktop entry passed validation and resolved to the new icon
  through Gio. Desktop/icon caches were refreshed without restarting the shell
  or replacing the installed runtime; live Dock appearance remains user acceptance.
