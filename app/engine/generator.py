"""Orchestrates a project set-up run:

  1. Create the project output folder  "<PJ> - <site>".
  2. Recreate the chosen department's filing structure (folders only) inside it.
  3. Copy each selected form in, stamp the project fields, and prefix the filename.
  4. Zip the result for download.

Forms are filed per structure into their exact destination subfolder
(config/library_map.json, generated from CBES_Library_Map.xlsx). For the selected
structure the engine tries, in order:
  * library_map.structures[<structure>].by_file[exact filename],
  * .by_prefix[longest matching code prefix] (Rules sheet),
  * the coarse group -> folder map (config/filing_map.json),
  * "05 Forms (Populated)/<group>" so nothing is ever lost.
A form lands in its exact subfolder where the structure has one, otherwise its
zone top folder, otherwise the safe fallback.

All template files are treated as read-only; nothing under TEMPLATES_ROOT is
modified. Stamping happens only on the copies in the output folder.
"""
from __future__ import annotations

import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from ..config import (
    get_settings,
    load_departments,
    load_field_map,
    load_filing_map,
    load_library_map,
)
from .fields import FieldMatcher, ProjectData
from .stamp_docx import stamp_docx
from .stamp_pptx import stamp_pptx
from .stamp_xlsx import stamp_xlsx
from .structure import STAMPABLE_EXT, SKIP_FILES, forms_root, resolve_master_dir

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_CODE_RE = re.compile(r"^(?:\d+\s+)?(HS|ENV|MS|IMS)\s+(\d+(?:\.\d+)*)", re.I)
POPULATED_DIRNAME = "05 Forms (Populated)"
MAX_PATH = 240  # keep well under the Windows 260-char limit


@dataclass
class FileResult:
    rel: str
    output_name: str
    fields_written: int
    status: str  # "ok" | "copied" | "error"
    message: str = ""


@dataclass
class RunReport:
    project_number: str
    site: str
    output_dir: str
    zip_path: str
    files: list[FileResult] = field(default_factory=list)

    @property
    def total_fields(self) -> int:
        return sum(f.fields_written for f in self.files)

    @property
    def ok_count(self) -> int:
        return sum(1 for f in self.files if f.status in ("ok", "copied"))

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.files if f.status == "error")


def safe_component(text: str) -> str:
    text = _ILLEGAL.sub("", text or "").strip().rstrip(".")
    return re.sub(r"\s+", " ", text)[:80] or "Untitled"


def _prefixed_name(pj: str, site: str, original: str, dest_dir: Path) -> str:
    """Prefix each file with the project number only, e.g. 'PJ-123456 - <original>'.
    Falls back to the bare original if the full path would exceed the Windows limit."""
    candidate = f"{pj} - {original}"
    if len(str(dest_dir / candidate)) <= MAX_PATH:
        return candidate
    return original


def _derive_code(filename: str) -> str | None:
    """Pull the CBES form code out of a filename, e.g. 'HS 11.4', 'MS 9.4', 'IMS 4.3'.
    Tolerates a leading numeric prefix like '04 HS 11.4 - ...'."""
    m = _CODE_RE.match(filename)
    return f"{m.group(1).upper()} {m.group(2)}" if m else None


def _prefix_candidates(code: str) -> list[str]:
    """Longest-first code prefixes for a Rules-sheet lookup:
    'HS 11.16.1' -> ['HS 11.16.1', 'HS 11.16', 'HS 11']."""
    pre, _, nums = code.partition(" ")
    parts = nums.split(".")
    return [f"{pre} {'.'.join(parts[:i])}" for i in range(len(parts), 0, -1)]


def _filing_target(dest: Path, library_map: dict, filing_map: dict,
                   master_sub: str | None, group_code: str | None,
                   original: str, group: Path) -> Path:
    """Directory a form is filed into, for the selected structure.

    1) Library Map (per structure): exact filename, then longest code-prefix.
    2) Coarse group -> folder filing_map.
    3) '05 Forms (Populated)/<group>' fallback so nothing is ever lost.
    A candidate is only used if its folder is actually present in the recreated
    structure; otherwise the next step is tried.
    """
    # 1) Per-form filing from the Library Map, scoped to this structure.
    struct_map = None
    if master_sub:
        struct_map = (library_map.get("structures") or {}).get(master_sub)
    if struct_map:
        rel = (struct_map.get("by_file") or {}).get(original)
        if not rel:
            code = _derive_code(original)
            if code:
                by_prefix = struct_map.get("by_prefix") or {}
                for cand in _prefix_candidates(code):
                    if cand in by_prefix:
                        rel = by_prefix[cand]
                        break
        if rel and (dest / rel).is_dir():
            return dest / rel
    # 2) Coarse group -> folder map.
    if master_sub and group_code:
        rel = (filing_map.get(master_sub) or {}).get(group_code)
        if rel and (dest / rel).is_dir():
            return dest / rel
    # 3) Safe fallback.
    return dest / POPULATED_DIRNAME / group


def _stamp_file(path: Path, matcher: FieldMatcher) -> int:
    ext = path.suffix.lower()
    if ext == ".docx":
        return stamp_docx(str(path), matcher)
    if ext in (".xlsx", ".xlsm"):
        return stamp_xlsx(str(path), matcher)
    if ext == ".pptx":
        return stamp_pptx(str(path), matcher)
    return 0


def _copy_structure(master_dir: Path, dest: Path) -> None:
    """Recreate the department folder skeleton (directories only)."""
    dest.mkdir(parents=True, exist_ok=True)
    if not master_dir or not master_dir.is_dir():
        return
    for d in sorted(p for p in master_dir.rglob("*") if p.is_dir()):
        rel = d.relative_to(master_dir)
        (dest / rel).mkdir(parents=True, exist_ok=True)


def generate(data: ProjectData, selected_rels: list[str]) -> RunReport:
    settings = get_settings()
    settings.OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    site = safe_component(data.site)
    pj = data.project_number
    project_folder = f"{pj} - {site}"
    dest = settings.OUTPUT_ROOT / project_folder

    if dest.exists():
        if settings.OVERWRITE_EXISTING:
            shutil.rmtree(dest)
        else:
            raise FileExistsError(
                f"A project folder '{project_folder}' already exists. "
                "Set OVERWRITE_EXISTING=true or use a different project number."
            )

    # 1 + 2: filing structure
    master_dir = resolve_master_dir(data.department, data.structure)
    _copy_structure(master_dir, dest)

    # 3: forms
    matcher = FieldMatcher(load_field_map(), data.as_map(), settings.STAMP_DATE)
    froot = forms_root()
    deps = load_departments()
    master_sub = (deps["departments"].get(data.department) or {}).get(data.structure)
    folder_to_code = {folder: code for code, folder in deps["form_folders"].items()}
    filing_map = load_filing_map()
    library_map = load_library_map()
    report = RunReport(project_number=pj, site=data.site, output_dir=str(dest), zip_path="")

    for rel in selected_rels:
        src = froot / rel
        group = Path(rel).parent  # e.g. "01 OHS"
        original = Path(rel).name
        if original.lower() in SKIP_FILES or original.startswith("~$"):
            continue
        target_dir = _filing_target(
            dest, library_map, filing_map, master_sub,
            folder_to_code.get(group.name), original, group,
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        out_name = _prefixed_name(pj, site, original, target_dir)
        out_path = target_dir / out_name

        if not src.is_file():
            report.files.append(FileResult(rel, out_name, 0, "error", "source not found"))
            continue
        try:
            shutil.copy2(src, out_path)
            if out_path.suffix.lower() in STAMPABLE_EXT:
                n = _stamp_file(out_path, matcher)
                report.files.append(FileResult(rel, out_name, n, "ok"))
            else:
                report.files.append(FileResult(rel, out_name, 0, "copied", "not a stampable type"))
        except Exception as e:  # keep going; report per-file
            report.files.append(FileResult(rel, out_name, 0, "error", str(e)))

    # 4: zip
    zip_path = settings.OUTPUT_ROOT / f"{project_folder}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in dest.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(settings.OUTPUT_ROOT))
    report.zip_path = str(zip_path)
    return report
