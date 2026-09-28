"""Field model, label normalisation and matching.

The population strategy is *label-driven*: CBES forms have no placeholder tokens
({{...}}). Instead each form has a label cell (e.g. "Project Number:") with an
adjacent blank/stale value cell. We normalise every candidate label and match it
exactly against the field map, then write the project value into the neighbour.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from datetime import date
from typing import Optional


# --------------------------------------------------------------------------- #
# Project data supplied by the user
# --------------------------------------------------------------------------- #
PJ_RE = re.compile(r"^PJ-\d{6}$", re.IGNORECASE)


@dataclass
class ProjectData:
    project_number: str          # e.g. "PJ-123456"
    site: str                    # site / store name
    postcode: str = ""
    site_address: str = ""       # full/area address (may be auto-filled from postcode)
    project_title: str = ""      # defaults to site if blank
    project_manager: str = ""
    quantity_surveyor: str = ""
    client: str = ""
    project_date: str = ""       # dd/mm/yyyy; only used when STAMP_DATE=true
    department: str = ""
    structure: str = ""          # "standard" | "lite"

    def __post_init__(self):
        self.project_number = self.project_number.strip().upper()
        self.site = self.site.strip()
        if not self.project_title:
            self.project_title = self.site
        if not self.project_date:
            self.project_date = date.today().strftime("%d/%m/%Y")

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not PJ_RE.match(self.project_number):
            errors.append("Project number must be in the form PJ-000000 (six digits).")
        if not self.site:
            errors.append("Site / store name is required.")
        return errors

    def as_map(self) -> dict[str, str]:
        return {
            "project_number": self.project_number,
            "project_title": self.project_title,
            "site": self.site,
            "site_address": self.site_address,
            "postcode": self.postcode,
            "project_manager": self.project_manager,
            "quantity_surveyor": self.quantity_surveyor,
            "client": self.client,
            "date": self.project_date,
        }


# --------------------------------------------------------------------------- #
# Label normalisation + matcher
# --------------------------------------------------------------------------- #
def normalise_label(text: str) -> str:
    """Lowercase, trim, drop a single trailing colon, collapse inner whitespace."""
    if text is None:
        return ""
    t = str(text).replace(" ", " ").strip()
    t = re.sub(r"\s+", " ", t)
    t = t.rstrip(":").strip()
    return t.lower()


class FieldMatcher:
    """Resolves a normalised label to the value that should be written."""

    def __init__(self, field_map: dict, values: dict[str, str], stamp_date: bool):
        self.values = values
        self._label_to_field: dict[str, str] = {}
        for entry in field_map.get("fields", []):
            fld = entry["field"]
            if not entry.get("enabled", True):
                continue
            if fld == "date" and not stamp_date:
                continue
            for label in entry.get("labels", []):
                self._label_to_field[normalise_label(label)] = fld
        # All labels (even disabled) so we never treat a label cell as a value target.
        self._all_labels: set[str] = set()
        for entry in field_map.get("fields", []):
            for label in entry.get("labels", []):
                self._all_labels.add(normalise_label(label))

    def is_label(self, text: str) -> bool:
        return normalise_label(text) in self._all_labels

    def value_for(self, text: str) -> Optional[str]:
        """Return the value to write for this label, or None if not a mapped label
        or the corresponding project value is empty."""
        fld = self._label_to_field.get(normalise_label(text))
        if not fld:
            return None
        val = (self.values.get(fld) or "").strip()
        return val or None


# --------------------------------------------------------------------------- #
# Inline "Label: value" replacement (used in pptx text frames & docx paragraphs)
# --------------------------------------------------------------------------- #
def inline_replacement(text: str, matcher: "FieldMatcher") -> Optional[str]:
    """If `text` looks like 'Project No: something', return the rewritten string
    with the project value after the colon, else None."""
    if ":" not in text:
        return None
    label_part, _, _rest = text.partition(":")
    val = matcher.value_for(label_part)
    if val is None:
        return None
    return f"{label_part.strip()}: {val}"
