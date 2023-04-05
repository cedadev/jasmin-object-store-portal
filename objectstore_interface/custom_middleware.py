from fastapi.applications import FastAPI, Request
from fastapi.middleware import Middleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

class RedirectWhenLoggedOut(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        allowed_urls = ["login", "redirect", "static"]
        currenturl = request.url._url.replace(str(request.base_url), "")
        currenturl = currenturl.replace(str("?"+request.url.query), "")
        print(currenturl)
        if any(url in currenturl for url in allowed_urls):
            return await call_next(request)
        if request.session.get("token") is None:
            return RedirectResponse("/login")
        return await call_next(request)