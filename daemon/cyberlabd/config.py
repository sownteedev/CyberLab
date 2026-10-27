from dataclasses import dataclass
from pathlib import Path
import stat
import tomllib


def trusted_path(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("Production paths must be absolute")
    if ".." in path.parts:
        raise ValueError("Production paths must not contain parent traversal")
    is_home = len(path.parts) > 1 and path.parts[1] == "home"
    for component in (*reversed(path.parents), path):
        status = component.lstat()
        if stat.S_ISLNK(status.st_mode):
            raise ValueError("Production files and ancestors must be root-owned, not writable by others, and not symlinks")
        if is_home:
            if status.st_mode & 0o002:
                raise ValueError("Production files and ancestors in home must not be world-writable")
        else:
            if status.st_uid != 0 or status.st_mode & 0o022:
                raise ValueError("Production files and ancestors must be root-owned, not writable by others, and not symlinks")


@dataclass(frozen=True)
class Config:
    catalog: Path
    allowed_uids: frozenset[int]
    allowed_images: frozenset[str]
    authoring: bool = False


def load_config(path: Path) -> Config:
    trusted_path(path)
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    if set(document) - {"catalog", "allowed_uids", "allowed_images", "authoring"} or not {"catalog", "allowed_uids", "allowed_images"} <= set(document):
        raise ValueError("Config requires catalog, allowed_uids, allowed_images and optional authoring")
    if type(document.get("authoring", False)) is not bool:
        raise ValueError("authoring must be a boolean")
    if not isinstance(document["catalog"], str):
        raise ValueError("catalog must be an absolute directory path")
    uids = document["allowed_uids"]
    images = document["allowed_images"]
    if not isinstance(uids, list) or not uids or any(type(uid) is not int or not 0 <= uid < 2**32 for uid in uids):
        raise ValueError("allowed_uids must contain numeric Unix UIDs")
    if not isinstance(images, list) or not images or any(not isinstance(image, str) or not image.strip() for image in images):
        raise ValueError("allowed_images must contain explicit image references")
    catalog = Path(document["catalog"])
    trusted_path(catalog)
    if not catalog.is_dir():
        raise ValueError("catalog must be a directory")
    for item in catalog.rglob("*"):
        trusted_path(item)
        mode = item.lstat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError("Production catalog contains a special file")
    return Config(catalog, frozenset(uids), frozenset(images), document.get("authoring", False))
