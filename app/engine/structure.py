"""Catalogue helpers: departments, structures and the forms tree."""
from __future__ import annotations

from pathlib import Path

from ..config import get_settings, load_departments

SKIP_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}
STAMPABLE_EXT = {".docx", ".xlsx", ".xlsm", ".pptx"}


def department_catalogue() -> list[dict]:
    """[{name, standard: bool, lite: bool}] for building the page-1 dropdown."""
    deps = load_departments()["departments"]
    out = []
    for name, cfg in deps.items():
        out.append(
            {
                "name": name,
                "standard": bool(cfg.get("standard")),
                "lite": bool(cfg.get("lite")),
            }
        )
    return out


def resolve_master_dir(department: str, structure: str) -> Path | None:
    """Absolute path to the master template folder for a dept + structure."""
    cfg = load_departments()
    dep = cfg["departments"].get(department)
    if not dep:
        return None
    sub = dep.get(structure)
    if not sub:
        return None
    return get_settings().TEMPLATES_ROOT / cfg["master_root"] / sub


def forms_root() -> Path:
    cfg = load_departments()
    return get_settings().TEMPLATES_ROOT / cfg["forms_root"]


def forms_tree() -> list[dict]:
    """Build the page-2 selection tree grouped by OHS/ENV/QUAL/IMS.

    Returns [{code, folder, files:[{name, rel}]}]. `rel` is the path relative to
    the forms root, used as the checkbox value.
    """
    cfg = load_departments()
    root = forms_root()
    tree = []
    for code, folder in cfg["form_folders"].items():
        group_dir = root / folder
        files = []
        if group_dir.is_dir():
            for p in sorted(group_dir.iterdir()):
                if p.is_file() and p.name.lower() not in SKIP_FILES and not p.name.startswith("~$"):
                    files.append({"name": p.name, "rel": f"{folder}/{p.name}"})
        tree.append({"code": code, "folder": folder, "files": files})
    return tree
