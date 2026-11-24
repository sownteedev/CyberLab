"""Per-user display policy; never accepts executables or host paths."""

import json
import os
from pathlib import Path
import tempfile


def preference(selected=None):
    root = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    if not root.is_absolute():
        root = Path.home() / '.config'
    path = root / 'cyberlab' / 'gui.json'
    warning = ''
    if selected is not None:
        if selected not in ('auto', 'xpra'):
            raise ValueError('Display policy must be auto or xpra')
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.gui-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w') as output:
                json.dump({'preferred': selected}, output)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    try:
        if path.stat().st_size > 4096:
            raise ValueError
        saved = json.loads(path.read_text())
        selected = saved['preferred']
        if selected not in ('auto', 'xpra'):
            raise ValueError
    except FileNotFoundError:
        selected = 'auto'
    except (OSError, ValueError, KeyError, TypeError):
        selected, warning = 'auto', 'Invalid display preference; using Auto without overwriting the saved file'
    return {'preferred': selected, 'warning': warning}
