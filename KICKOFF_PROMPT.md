# VS Code kickoff prompt

Paste the block below into **Claude Code** (or Copilot Chat's agent mode) with this
repo open as the workspace folder. It fans work out across parallel subagents to
get you running fast, then leaves the server up.

---

```
You are working in the CBES Project Set-Up repo (FastAPI + python-docx/openpyxl/python-pptx).
Goal: get it running against my real templates and verify it, using parallel subagents for speed.

Context:
- Templates live at:
  C:\Users\FlawsA\OneDrive - City Facilities Management Holdings Ltd (1)\10. Project Set up Folder & Documents
  (this folder contains "00 Master Projects FIle Template 0524 (Opt 2)", "05 Forms",
   and the lookup files PMs.xlsx, QS.xlsx, "CBES Customer List.xlsx")
- Windows, PowerShell. Python 3.10+ installed.

Spawn these subagents to run IN PARALLEL, then report back:

AGENT 1 — Environment & run:
  1. Create a venv: py -3 -m venv .venv ; .venv\Scripts\Activate.ps1
  2. pip install -r requirements.txt
  3. Copy .env.example to .env. In .env set:
       SECRET_KEY = (generate: python -c "import secrets;print(secrets.token_hex(32))")
       TEMPLATES_ROOT = C:\Users\FlawsA\OneDrive - City Facilities Management Holdings Ltd (1)\10. Project Set up Folder & Documents
       AUTH_MODE = local
       LOCAL_PASSWORD = (pick one)
  4. Do NOT commit .env (already in .gitignore).

AGENT 2 — Test & verify engine:
  1. Run: python -m pytest -q   (expect all green)
  2. Write a scratch script that imports app.engine.generator and does ONE dry run
     against the real TEMPLATES_ROOT with project PJ-999999, a test site + postcode,
     a PM/QS/customer from the lookup files, selecting ~4 forms across OHS/ENV/QUAL/IMS.
     Confirm: output folder created, filenames prefixed "PJ-999999 - ...", fields stamped > 0,
     zero errors. Delete the scratch output afterwards. Report the per-file field counts.

AGENT 3 — Pre-flight checks:
  1. Confirm the three lookup files load (app.engine.lookups.project_managers/quantity_surveyors/customers return non-empty).
  2. Confirm OneDrive files are hydrated locally (Files On-Demand can dehydrate them). If any
     "05 Forms" file is cloud-only, right-click "05 Forms" -> "Always keep on this device".
  3. Confirm postcode lookup works on my network: python -c "from app.engine.geo import lookup_postcode as f;print(f('TS18 2PB'))"
     — if 'valid' is False due to a proxy, note the corporate proxy and set HTTPS_PROXY in .env accordingly.

When all three finish, start the server yourself and leave it running:
  python -m uvicorn app.main:app --reload --port 8000
Then tell me: the http://localhost:8000 URL, the pytest result, the dry-run field counts,
and anything from pre-flight I need to action (hydration / proxy).

If anything fails, fix it in the repo, re-run that agent's checks, and summarise the change.
Do not modify the files under TEMPLATES_ROOT — only read them.
```

---

## Even quicker (single command, no real templates yet)

If you just want to click through the UI first with demo data:

```powershell
py -3 -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\make_sample_root.py
copy .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000>, sign in (name + the password `cbes`), and run a project.
