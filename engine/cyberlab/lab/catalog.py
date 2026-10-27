from pathlib import Path
import os
import stat

from .loader import LabError, load_lab
from .models import Lab
from .package import open_directory, read_directory, PackageLimit
from .removal import remove_tree


class LabCatalogError(LabError):
    """The catalog cannot be read or contains an invalid entry."""


class LabNotFoundError(LabError):
    """No Lab in a valid catalog has the requested identity."""


class LabInUseError(LabError):
    """The Lab cannot be removed because it is still referenced."""

MAX_PACKAGE_BYTES = 2 * 1024 * 1024
MAX_PACKAGE_ENTRIES = 128


def catalog_entries(root: str | Path):
    """Read immediate, non-hidden child projects and validate the whole catalog."""
    root = Path(root)
    try:
        entries = sorted(root.iterdir(), key=lambda entry: entry.name)
    except OSError:
        raise LabCatalogError(f"Cannot read catalog directory {str(root)!r}") from None

    labs = {}
    sources = {}
    for entry in entries:
        if entry.name.startswith("."):
            continue
        try:
            mode = entry.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise LabCatalogError(f"Catalog symlink is not allowed: {str(entry)!r}")
            if not stat.S_ISDIR(mode):
                continue
            definition = entry / "lab.yaml"
            try:
                mode = definition.lstat().st_mode
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(mode):
                raise LabCatalogError(
                    f"Lab definition must be a regular file: {str(definition)!r}"
                )
        except OSError:
            raise LabCatalogError(f"Cannot inspect catalog entry {str(entry)!r}") from None

        try:
            lab = load_lab(definition)
        except LabError as error:
            raise LabCatalogError(
                f"Invalid catalog entry {str(definition)!r}: {error}"
            ) from None
        lab_id = lab.metadata.id
        if lab_id in labs:
            raise LabCatalogError(
                f"Duplicate Lab ID {lab_id!r} in {str(sources[lab_id])!r} "
                f"and {str(definition)!r}"
            )
        labs[lab_id] = lab
        sources[lab_id] = definition

    return tuple((sources[lab_id].parent, labs[lab_id]) for lab_id in sorted(labs))

def list_labs(root: str | Path) -> tuple[Lab, ...]:
    return tuple(lab for _, lab in catalog_entries(root))


def get_lab(root: str | Path, lab_id: str) -> Lab:
    """Find an identity in a fully validated catalog, never as a filesystem path."""
    for lab in list_labs(root):
        if lab.metadata.id == lab_id:
            return lab
    raise LabNotFoundError("Lab ID not found in catalog")


def lab_directory(root: str | Path, lab_id: str) -> Path:
    for directory, lab in catalog_entries(root):
        if lab.metadata.id == lab_id:
            return directory
    raise LabNotFoundError("Lab ID not found in catalog")


def read_package(root: str | Path, lab_id: str):
    directory = lab_directory(root, lab_id)
    try:
        definition, assets, digest = read_directory(directory)
        return definition, tuple(sorted(assets.items())), digest
    except (OSError, ValueError, PackageLimit) as error:
        raise LabCatalogError(f"Lab package cannot be edited safely: {error}") from None


def package_digest(root: str | Path, lab_id: str) -> str:
    return read_package(root, lab_id)[2]


def remove_lab(root: str | Path, lab_id: str) -> None:
    """Remove an installed Lab directory after identity validation."""
    root = Path(root)
    get_lab(root, lab_id)
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if entry.name.startswith(".") or not entry.is_dir() or entry.is_symlink():
            continue
        definition = entry / "lab.yaml"
        if not definition.is_file() or definition.is_symlink():
            continue
        lab = load_lab(definition)
        if lab.metadata.id == lab_id:
            parent = open_directory(root)
            try:
                remove_tree(parent, entry.name)
            finally:
                os.close(parent)
            return
    raise LabNotFoundError("Lab directory not found in catalog")
