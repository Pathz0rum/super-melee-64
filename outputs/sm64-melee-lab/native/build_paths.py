"""An installer-owned, temporary drive alias keeps Make paths portable on Windows."""
from pathlib import Path
import os


def project_root(filename):
    root = Path(filename).resolve().parents[3]
    alias = os.environ.get('SMB_WINDOWS_BUILD_ROOT')
    if os.name == 'nt' and alias:
        candidate = Path(alias)
        if not candidate.is_absolute() or not os.path.samefile(candidate, root):
            raise RuntimeError('The temporary Windows build drive does not refer to this source kit.')
        return candidate
    return root
