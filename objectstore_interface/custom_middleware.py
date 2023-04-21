from fastapi.applications import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
import json

class RedirectWhenLoggedOut(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        allowed_urls = ["login", "redirect", "static"]
        currenturl = request.url._url.replace(str(request.base_url), "")
        currenturl = currenturl.replace(str("?"+request.url.query), "")
        if any(url in currenturl for url in allowed_urls):
            return await call_next(request)
        if request.session.get("token") is None:
            return RedirectResponse("/login")
        return await call_next(request)
    

class MockSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, http_request: Request, call_next: RequestResponseEndpoint):
        if http_request.headers.get("token") is not None:
             options = json.loads(http_request.headers["token"])
             for k,v in options["options"].items():
                http_request.session[k] = v
        return await call_next(http_request)