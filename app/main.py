"""FastAPI application: two-page wizard + generation + download."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .auth import router as auth_router, require_user
from .config import BASE_DIR, get_settings
from .engine.fields import ProjectData
from .engine.generator import generate
from .engine.geo import lookup_postcode
from .engine.lookups import customers, project_managers, quantity_surveyors
from .engine.structure import department_catalogue, forms_tree


def _lookup_ctx() -> dict:
    return {
        "pms": project_managers(),
        "qss": quantity_surveyors(),
        "customers": customers(),
    }

settings = get_settings()
app = FastAPI(title="CBES Project Set-Up")
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, max_age=60 * 60 * 8)
app.include_router(auth_router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@app.exception_handler(HTTPException)
async def _auth_redirect(request: Request, exc: HTTPException):
    # require_user raises 307 with a Location header when unauthenticated.
    if exc.status_code == 307 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(exc.headers["Location"], status_code=303)
    return HTMLResponse(f"<h1>{exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code)


@app.get("/", response_class=HTMLResponse)
async def page1(request: Request):
    user = require_user(request)
    return templates.TemplateResponse(request,
        "page1.html",
        {
            "request": request,
            "user": user,
            "departments": department_catalogue(),
            "data": request.session.get("project", {}),
            **_lookup_ctx(),
        },
    )


@app.get("/api/postcode")
async def api_postcode(request: Request, pc: str = ""):
    require_user(request)
    return lookup_postcode(pc)


@app.post("/step2", response_class=HTMLResponse)
async def step2(
    request: Request,
    department: str = Form(...),
    structure: str = Form(...),
    project_number: str = Form(...),
    site: str = Form(...),
    postcode: str = Form(""),
    site_address: str = Form(""),
    project_title: str = Form(""),
    project_manager: str = Form(""),
    quantity_surveyor: str = Form(""),
    client: str = Form(""),
):
    user = require_user(request)
    data = ProjectData(
        project_number=project_number,
        site=site,
        postcode=postcode,
        site_address=site_address,
        project_title=project_title,
        project_manager=project_manager,
        quantity_surveyor=quantity_surveyor,
        client=client,
        department=department,
        structure=structure,
    )
    errors = data.validate()
    if errors:
        return templates.TemplateResponse(request, 
            "page1.html",
            {
                "request": request,
                "user": user,
                "departments": department_catalogue(),
                "data": {
                    "department": department, "structure": structure,
                    "project_number": project_number, "site": site, "postcode": postcode,
                    "site_address": site_address,
                    "project_title": project_title, "project_manager": project_manager,
                    "quantity_surveyor": quantity_surveyor, "client": client,
                },
                "errors": errors,
                **_lookup_ctx(),
            },
            status_code=400,
        )
    request.session["project"] = data.as_map() | {
        "department": department, "structure": structure,
    }
    return templates.TemplateResponse(request, 
        "page2.html",
        {"request": request, "user": user, "data": data, "tree": forms_tree()},
    )


@app.post("/generate", response_class=HTMLResponse)
async def do_generate(request: Request):
    user = require_user(request)
    proj = request.session.get("project")
    if not proj:
        return RedirectResponse("/", status_code=303)

    form = await request.form()
    selected = form.getlist("forms")
    if not selected:
        return templates.TemplateResponse(request, 
            "page2.html",
            {
                "request": request, "user": user,
                "data": _rebuild(proj), "tree": forms_tree(),
                "error": "Select at least one form to generate.",
            },
            status_code=400,
        )

    data = _rebuild(proj)
    try:
        report = generate(data, selected)
    except FileExistsError as e:
        return templates.TemplateResponse(request, 
            "page2.html",
            {"request": request, "user": user, "data": data, "tree": forms_tree(), "error": str(e)},
            status_code=409,
        )
    request.session["zip_path"] = report.zip_path
    return templates.TemplateResponse(request, 
        "result.html", {"request": request, "user": user, "report": report, "data": data}
    )


@app.get("/download")
async def download(request: Request):
    require_user(request)
    zip_path = request.session.get("zip_path")
    if not zip_path or not Path(zip_path).is_file():
        raise HTTPException(status_code=404, detail="No generated package available.")
    return FileResponse(zip_path, filename=Path(zip_path).name, media_type="application/zip")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "auth_mode": settings.AUTH_MODE, "templates_root": str(settings.TEMPLATES_ROOT)}


def _rebuild(proj: dict) -> ProjectData:
    return ProjectData(
        project_number=proj.get("project_number", ""),
        site=proj.get("site", ""),
        postcode=proj.get("postcode", ""),
        site_address=proj.get("site_address", ""),
        project_title=proj.get("project_title", ""),
        project_manager=proj.get("project_manager", ""),
        quantity_surveyor=proj.get("quantity_surveyor", ""),
        client=proj.get("client", ""),
        department=proj.get("department", ""),
        structure=proj.get("structure", ""),
    )
