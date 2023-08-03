import typing
from fastapi.applications import Request
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction, RequestResponseEndpoint
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from http import HTTPStatus
import json
from fastapi.templating import Jinja2Templates

from starlette.requests import Request
from starlette.responses import Response

from starlette.datastructures import URL
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

templates = Jinja2Templates(directory="objectstore_interface/templates")

class RedirectWhenLoggedOut:
    """When the session token is non-existent will redirect users to login before they can access the site."""
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, recieve: Receive, send: Send):
        allowed_urls = ["/login", "/redirect", "/static"]
        currenturl = scope["path"]
        if any(url in currenturl for url in allowed_urls):
            await self.app(scope, recieve, send)
            return
        if scope["session"].get("token") is None:
            response = RedirectResponse("/login", status_code=303)
            await response(scope, recieve, send)
            return
        else:
            await self.app(scope, recieve, send)
            return
    

class MockSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, http_request: Request, call_next: RequestResponseEndpoint):
        if http_request.headers.get("token") is not None:
             options = json.loads(http_request.headers["token"])
             for k,v in options["options"].items():
                http_request.session[k] = v
        return await call_next(http_request)