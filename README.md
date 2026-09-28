# CBES Project Set-Up

A small internal web app that spins up a new project pack from the CBES master
templates. A user signs in, enters the project particulars (department, folder
structure, project number, site, postcode, PM, QS), picks which forms they want
from the four form sets (OHS / ENV / QUAL / IMS), and the app:

1. recreates the chosen department's **filing structure**,
2. copies each selected form in,
3. **stamps the project details** into every file (Word, Excel, PowerPoint), and
4. **prefixes every filename** with the project number (`PJ-000000 - <original>`),
5. and hands back a downloadable `.zip` of the whole pack.

**Selection helpers**
- **Project Manager / Quantity Surveyor / Customer** are searchable dropdowns fed
  from `PMs.xlsx`, `QS.xlsx` and `CBES Customer List.xlsx` in `TEMPLATES_ROOT`
  (type-ahead; free text still allowed). Configured in `config/departments.json → lookups`.
- **Postcode lookup** auto-fills the site area and shows a live map with
  **Google Maps / Google Earth / OpenStreetMap** links. Uses the free
  postcodes.io service (no key); add a `GETADDRESS_API_KEY` for full PAF
  street addresses. Degrades gracefully offline — manual entry always works.

Templates are never modified — all stamping happens on the copies.

---

## Why this design

The CBES forms have **no placeholder tokens** (`{{...}}`) and some "templates"
still hold live data from previous jobs (e.g. `HS 11.1` had *"Asda Yorkshire Rose
Stockton"* and PM *"Brian Rooney"* baked in). So a blind find/replace is not safe.

Instead the engine is **label-driven**: it finds a label cell (`Project Number:`,
`Site:`, `Project Manager:` …), then writes the project value into the adjacent
value cell — **overwriting stale data as well as filling blanks**. Labels are
matched *exactly* after normalisation (lowercase, trimmed, trailing colon removed)
so there are no false hits like `PM` inside another word. All label→field mappings
live in [`config/field_map.json`](config/field_map.json) — extend coverage there
without touching code.

---

## Stack

- **Python 3.10+ / FastAPI** (single service — easiest to run in VS Code & push to GitHub)
- **python-docx / openpyxl / python-pptx** — the gold standard for editing existing Office files
- **Jinja2** server-rendered UI (2-page wizard), vanilla JS, no build step
- **Authlib** — Microsoft Entra ID (OIDC) with a local-login fallback

```
cbes-project-setup/
├─ app/
│  ├─ main.py            # routes: /login, / (step1), /step2, /generate, /download
│  ├─ auth.py            # Entra ID OIDC + local fallback
│  ├─ config.py          # settings from .env
│  ├─ engine/
│  │  ├─ fields.py       # ProjectData, label normalisation, FieldMatcher
│  │  ├─ stamp_docx.py   # tables + headers/footers + inline
│  │  ├─ stamp_xlsx.py   # label → cell to the right / below
│  │  ├─ stamp_pptx.py   # tables + inline "Label: value"
│  │  ├─ structure.py    # department catalogue + forms tree
│  │  ├─ lookups.py      # PM / QS / Customer dropdown data from xlsx
│  │  ├─ geo.py          # postcode → area/lat-long + Maps/Earth links
│  │  └─ generator.py    # orchestration: copy tree → stamp → prefix → zip
│  ├─ templates/         # base, login, page1, page2, result
│  └─ static/            # styles.css, app.js
├─ config/
│  ├─ departments.json   # dept + standard/lite → master folder
│  └─ field_map.json     # label patterns → project fields
├─ tests/                # pytest: matcher, per-format stampers, end-to-end
├─ scripts/make_sample_root.py   # builds a demo TEMPLATES_ROOT to test without OneDrive
├─ run.bat / run.sh
├─ requirements.txt
└─ .env.example
```

---

## Quick start (Windows)

```bat
git clone <your-repo-url> cbes-project-setup
cd cbes-project-setup
run.bat
```

`run.bat` creates a virtual env, installs dependencies, copies `.env.example` to
`.env`, and starts the server at <http://localhost:8000>.

**First run without the OneDrive templates** (recommended for a smoke test):

```bat
python scripts\make_sample_root.py
```

This builds `./sample_root` (the default `TEMPLATES_ROOT`) with a handful of
CBES-style forms so you can click through the whole flow immediately.

**Point it at the real templates** — edit `.env`:

```
TEMPLATES_ROOT=C:\Users\FlawsA\OneDrive - City Facilities Management Holdings Ltd (1)\10. Project Set up Folder & Documents
```

> OneDrive note: with *Files On-Demand*, cloud-only files hydrate automatically
> when the app reads them on Windows. To avoid first-run delays, right-click the
> `05 Forms` folder → **Always keep on this device**.

---

## Configuration (`.env`)

| Key | Purpose |
|-----|---------|
| `SECRET_KEY` | Session signing key. Generate: `python -c "import secrets;print(secrets.token_hex(32))"` |
| `TEMPLATES_ROOT` | Folder containing `00 Master…` **and** `05 Forms` |
| `OUTPUT_ROOT` | Where generated project folders + zips are written |
| `AUTH_MODE` | `local` (testing) or `entra` (SSO) |
| `LOCAL_PASSWORD` | Shared password when `AUTH_MODE=local` |
| `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET` | Entra ID app registration |
| `ENTRA_REDIRECT_URI` | `http://localhost:8000/auth/callback` |
| `STAMP_DATE` | If `true`, also stamps `Date:` fields (default `false` — many are inspection dates) |
| `OVERWRITE_EXISTING` | If `true`, regenerate over an existing project folder |
| `GETADDRESS_API_KEY` | *(optional)* getAddress.io key for full PAF street addresses |
| `GOOGLE_MAPS_API_KEY` | *(optional)* reserved for a Google satellite/earth embed |

### Wiring Microsoft Entra ID (external login)

1. Entra admin centre → **App registrations** → **New registration**.
2. Redirect URI (**Web**): `http://localhost:8000/auth/callback`.
3. **Certificates & secrets** → new client secret.
4. **API permissions** → Microsoft Graph → delegated: `openid`, `profile`, `email`, `User.Read` → grant admin consent.
5. Put `Tenant ID`, `Client ID`, `Client secret` in `.env` and set `AUTH_MODE=entra`.

Only `auth.py` knows about auth; swapping IdP (e.g. Okta) means changing the one
`oauth.register(...)` block.

---

## Extending

- **New department / structure** → add to `config/departments.json` (map to the
  master folder name; `null` = that structure isn't offered).
- **More fields stamped** → add label strings under the matching `field` in
  `config/field_map.json`. This is the path to full per-form coverage (v2).
- **Where populated forms land** → currently `05 Forms (Populated)/<group>/…` in
  the output. To file each form into its correct department subfolder, extend
  `generator.generate()` with a per-form destination map.

---

## Testing

```bat
python -m pytest -q
```

Covers label normalisation, exact matching, each format stamper (incl.
stale-value overwrite and the `Date:` opt-out), and a full end-to-end
`generate()` run (structure recreated, filenames prefixed, fields written, zip
produced).

---

## Push to GitHub

```bat
git init
git add .
git commit -m "CBES Project Set-Up: label-driven template stamping app"
git branch -M main
git remote add origin https://github.com/<you>/cbes-project-setup.git
git push -u origin main
```

`.gitignore` already excludes `.env`, `output/`, `sample_root/`, and caches.

---

## Known limitations (v1) / v2 backlog

- **Core header fields only** — Project No, Title, Site, Postcode, PM, QS, Client.
  Party-block layouts (e.g. QS name inside a Name/Address/Email block) aren't
  auto-filled yet; add them via `field_map.json` + a per-form map.
- **Legacy `.doc` / `.xls`** (a few files in the set) aren't stamped — resave as
  `.docx` / `.xlsx`, or add a LibreOffice-headless conversion step.
- **PDFs** are copied, not stamped (they're read-only arrangements).
- Generic `Address:` is deliberately **not** mapped (too ambiguous across parties).

---

## Resources

- FastAPI tutorial (official): <https://fastapi.tiangolo.com/tutorial/>
- FastAPI full course (freeCodeCamp, YouTube): <https://www.youtube.com/watch?v=0sOvCWFmrtA>
- python-docx docs: <https://python-docx.readthedocs.io/>
- Microsoft Entra ID + Python (MSAL/OIDC): <https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-web-app-python-sign-in>
