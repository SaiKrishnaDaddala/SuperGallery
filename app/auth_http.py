"""HTTP boundary for authentication, CSRF protection and secure enrollment."""
import ipaddress
import os
from urllib.parse import unquote, urlsplit

from fastapi import Body, HTTPException, Request
from fastapi.responses import JSONResponse

from . import scope, network
from .config import APP_PASSWORD, CONFIG_DIR
from .security import CHALLENGE_COOKIE, CHALLENGE_TTL, COOKIE, SESSION_TTL, Security

security = Security(CONFIG_DIR, APP_PASSWORD)


# Scripts only from this origin; inline styles stay allowed because views set style attributes.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "media-src 'self' blob:; font-src 'self' data:; connect-src 'self'; frame-src 'self'; worker-src 'self'; "
       "manifest-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; ")


def private_transport(request):
    if request.url.scheme == "https":
        return True
    try:
        return ipaddress.ip_address(request.client.host).is_loopback and request.url.hostname in ("localhost", "127.0.0.1", "::1", "testserver")
    except ValueError:
        return request.client.host == "testclient" and request.url.hostname == "testserver"


def secure_url(request):
    if getattr(request.state,'remote',False):
        return request.state.public_origin+'/#/settings'
    host = request.url.hostname or "localhost"
    if ":" in host:
        host = "[" + host + "]"
    return f"https://{host}:{int(os.environ.get('HTTPS_PORT', '8843'))}/#/settings"


def require_private(request):
    if not private_transport(request):
        raise HTTPException(426, "Open SuperGallery over HTTPS to manage authenticator security.")


def client(request):
    return request.client.host if request.client else "unknown"


def session_response(request, result):
    result = dict(result)
    token = result.pop("session", None)
    challenge = result.pop("challenge", None)
    response = JSONResponse({"ok": bool(token), **result})
    if token:
        response.set_cookie(COOKIE, token, max_age=SESSION_TTL, httponly=True, secure=request.url.scheme == "https", samesite="strict", path="/")
        response.delete_cookie(CHALLENGE_COOKIE, path="/api")
    if challenge:
        response.delete_cookie(COOKIE, path="/")
        response.set_cookie(CHALLENGE_COOKIE, challenge, max_age=CHALLENGE_TTL, httponly=True, secure=request.url.scheme == "https", samesite="strict", path="/api")
    response.headers["Cache-Control"] = "no-store"
    return response


def install(app):
    public = {"/api/auth", "/api/login", "/api/login/verify", "/api/setup"}

    @app.middleware("http")
    async def auth(request: Request, call_next):
        try:
            network.apply_transport(request)
        except HTTPException as exc:
            return JSONResponse({'detail':exc.detail},status_code=exc.status_code,headers={'Cache-Control':'no-store'})
        if request.state.remote and not security.enabled():
            return JSONResponse({'detail':'Remote access requires two-step verification. Enable it using the local NAS address.'},status_code=403,headers={'Cache-Control':'no-store'})
        path = request.url.path
        if path.startswith("/api/"):
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                origin = request.headers.get("origin")
                # Browser forms and fetches include Origin. CLI clients explicitly opt in.
                if (origin and origin.rstrip("/") != str(request.base_url).rstrip("/")) or (not origin and request.headers.get("x-sg-request") != "1"):
                    return JSONResponse({"detail": "Request origin could not be verified."}, status_code=403, headers={"Cache-Control":"no-store"})
            if security.enabled() and not private_transport(request) and path != "/api/auth":
                return JSONResponse({"detail": "Two-step verification requires HTTPS. Open the secure app address.", "secure_url": secure_url(request)}, status_code=426, headers={"Cache-Control":"no-store"})
            request.state.session = security.session(request.cookies.get(COOKIE), touch=path not in ("/api/auth", "/api/status", "/api/people/status", "/api/search/status", "/api/visual/status", "/api/ocr/status") and not path.startswith("/api/tasks/"))
            if path not in public and not request.state.session:
                return JSONResponse({"detail":"Login required"}, status_code=401, headers={"Cache-Control":"no-store"})
            if path not in public:
                from . import features
                try:
                    features.boundary(path)
                except HTTPException as exc:
                    return JSONResponse({'detail': exc.detail}, status_code=exc.status_code, headers={'Cache-Control':'no-store'})
            from . import backups
            if request.method not in ('GET','HEAD','OPTIONS') and path not in public | {'/api/logout','/api/backups/cancel-restore'} and backups.pending():
                return JSONResponse({'detail':'An app-data restore is waiting. Restart SuperGallery in Docker to apply it, or cancel it in Settings.'},status_code=409)
        hdr = request.headers.get("x-sg-users", "")
        scope.set_owners([unquote(value) for value in hdr.split(",") if value] or None)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if path in ("/", "/static/offline.html"):
            ancestors = ["'self'"]
            for origin in os.getenv('FRAME_ANCESTORS', '').split(','):
                origin = origin.strip()
                parsed = urlsplit(origin)
                if parsed.scheme in ('http', 'https') and parsed.netloc and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and parsed.path in ('', '/') and not any(c.isspace() for c in origin):
                    ancestors.append(f'{parsed.scheme}://{parsed.netloc}')
            response.headers["Content-Security-Policy"] = CSP + 'frame-ancestors ' + ' '.join(ancestors)
        if path.startswith("/api/") or path == "/":
            response.headers["Cache-Control"] = "no-store"
        elif path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/api/auth")
    def state(request: Request):
        return {"required":True, "setup":not security.configured(), "ok":bool(request.state.session) and (private_transport(request) or not security.enabled()),
                "https_required":security.enabled() and not private_transport(request), "secure_url":secure_url(request)}

    @app.post("/api/login")
    def login(request: Request, body: dict = Body(...)):
        return session_response(request, security.login(body.get("password"), client(request)))

    @app.post("/api/login/verify")
    def verify(request: Request, body: dict = Body(...)):
        require_private(request)
        token = security.verify_login(request.cookies.get(CHALLENGE_COOKIE), body.get("code"), client(request))
        return session_response(request, {"session":token})

    @app.post("/api/setup")
    def setup(request: Request, body: dict = Body(...)):
        require_private(request)
        security.throttle("security", client(request))
        with security.tx() as c:
            if security.configured():
                raise HTTPException(403, "A password is already set.")
            security.write_password(body.get("password"))
            token = security._new_session(c, False)
        return session_response(request, {"session":token})

    @app.post("/api/password")
    def password(request: Request, body: dict = Body(...)):
        require_private(request)
        if APP_PASSWORD:
            raise HTTPException(400, "The password is managed by APP_PASSWORD in Docker settings.")
        security.reauthenticate(body.get("old"), client(request))
        # Keep consumption and session revocation in the same transaction.
        result = None
        with security.tx() as c:
            enabled = bool(security.get(c, "totp"))
            if not enabled or security._verify_factor(c, body.get("code")):
                security.write_password(body.get("new"))
                security._revoke(c)
                result = {"session":security._new_session(c, enabled)}
        if result is None:
            raise HTTPException(403, "Enter a valid authenticator or recovery code.")
        return session_response(request, result)

    @app.post("/api/logout")
    def logout(request: Request):
        security.logout(request.cookies.get(COOKIE))
        response = JSONResponse({"ok":True})
        response.delete_cookie(COOKIE, path="/")
        response.delete_cookie(CHALLENGE_COOKIE, path="/api")
        return response

    @app.get("/api/security")
    def status(request: Request):
        return {**security.status(), "secure_transport":private_transport(request), "secure_url":secure_url(request)}

    @app.post("/api/security/totp/setup")
    def enrollment(request: Request, body: dict = Body(...)):
        require_private(request)
        return security.begin_enrollment(request.state.session["id"], body.get("password"), client(request), request.url.hostname or "My NAS")

    @app.post("/api/security/totp/confirm")
    def confirm(request: Request, body: dict = Body(...)):
        require_private(request)
        return session_response(request, security.confirm_enrollment(request.state.session["id"], body.get("code"), client(request)))

    @app.post("/api/security/totp/cancel")
    def cancel(request: Request):
        with security.tx() as c:
            c.execute("DELETE FROM enrollment WHERE session_id=?", (request.state.session["id"],))
        return {"ok":True}

    @app.post("/api/security/{action}")
    def manage(action: str, request: Request, body: dict = Body(...)):
        require_private(request)
        if action=='disable' and network.settings()['enabled']:
            raise HTTPException(409,'Turn off Remote access in Settings before disabling two-step verification.')
        if action not in ("disable", "recovery", "revoke"):
            raise HTTPException(404, "Unknown security action")
        result = security.manage(action, request.state.session["id"], body.get("password"), body.get("code"), client(request))
        return session_response(request, result)
