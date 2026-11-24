"""Run password dialog checks offscreen, with disposable preferences."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

from check_notifications import run_probe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio', type=Path, default=Path(__file__).resolve().parents[1] / 'ui/studio')
    parser.add_argument('--artifacts', type=Path)
    arguments = parser.parse_args()
    studio = arguments.studio.resolve()
    with tempfile.TemporaryDirectory(prefix='cyberlab-edit-access-') as directory:
        root = Path(directory)
        for name in ('home', 'config', 'cache', 'data', 'runtime', 'probe', 'artifacts'):
            (root / name).mkdir(mode=0o700)
        (root / 'probe/tst_EditAccess.qml').write_text(
            f'import {json.dumps((studio / "testing").as_uri())} as Checks\n'
            f'Checks.EditAccessTest {{ screenshotFolder: {json.dumps(str(root / "artifacts"))} }}\n')
        environment = dict(os.environ)
        for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH'):
            environment.pop(name, None)
        environment.update(HOME=str(root / 'home'), XDG_CONFIG_HOME=str(root / 'config'),
                           XDG_CONFIG_DIRS=str(root / 'config'), XDG_CACHE_HOME=str(root / 'cache'),
                           XDG_DATA_HOME=str(root / 'data'), XDG_RUNTIME_DIR=str(root / 'runtime'),
                           QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QT_QUICK_CONTROLS_STYLE='Basic')
        code, output = run_probe(['/usr/lib/qt6/bin/qmltestrunner', '-input', str(root / 'probe')], environment, root)
        print(output)
        if arguments.artifacts:
            shutil.copytree(root / 'artifacts', arguments.artifacts, dirs_exist_ok=True)
        return code or int('QWARN' in output)


if __name__ == '__main__':
    raise SystemExit(main())
