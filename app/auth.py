"""Authentication: Microsoft Entra ID (OIDC) with a local-login fallback.

AUTH_MODE=local  -> shared-password form login (for testing).
AUTH_MODE=entra  -> Entra ID / Azure AD single sign-on via Authlib.

Both modes end with request.session["user"] = {"name", "email"} and are consumed
by the require_user dependency, so the rest of the app is auth-agnostic.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import BASE_DIR, get_settings

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
router = APIRouter()

_oauth = None


def _get_oauth():
    global _oauth
    if _oauth is None:
        from authlib.integrations.starlette_client import OAuth

        s = get_settings()
        oauth = OAuth()
        oauth.register(
            name="entra",
            client_id=s.ENTRA_CLIENT_ID,
            client_secret=s.ENTRA_CLIENT_SECRET,
            server_metadata_url=s.entra_metadata_url,
            client_kwargs={"scope": "openid email profile"},
        )
        _oauth = oauth
    return _oauth


def require_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        # Signal to the route to redirect; handled via exception below.
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    return user


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    s = get_settings()
    if request.session.get("user"):
        return RedirectResponse("/", status_code=303)
    if s.AUTH_MODE == "entra":
        redirect_uri = s.ENTRA_REDIRECT_URI
        return await _get_oauth().entra.authorize_redirect(request, redirect_uri)
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None, "local_email": s.LOCAL_EMAIL})


@router.post("/login", response_class=HTMLResponse)
async def login_local(request: Request, username: str = Form(...), password: str = Form(...)):
    s = get_settings()
    if s.AUTH_MODE == "entra":
        raise HTTPException(status_code=400, detail="Local login disabled (AUTH_MODE=entra).")
    if password != s.LOCAL_PASSWORD or not username.strip():
        return templates.TemplateResponse(request,
            "login.html",
            {"request": request, "error": "Invalid email or password.",
             "local_email": s.LOCAL_EMAIL, "username": username},
            status_code=401,
        )
    uname = username.strip()
    if "@" in uname:
        email = uname
        name = uname.split("@")[0].replace(".", " ").replace("_", " ").title()
    else:
        name = uname
        email = s.LOCAL_EMAIL
    request.session["user"] = {"name": name, "email": email}
    return RedirectResponse("/", status_code=303)


@router.get("/auth/callback")
async def auth_callback(request: Request):
    s = get_settings()
    if s.AUTH_MODE != "entra":
        return RedirectResponse("/login", status_code=303)
    token = await _get_oauth().entra.authorize_access_token(request)
    claims = token.get("userinfo") or {}
    request.session["user"] = {
        "name": claims.get("name") or claims.get("preferred_username") or "Unknown",
        "email": claims.get("email") or claims.get("preferred_username") or "",
    }
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse("/login", status_code=303)
