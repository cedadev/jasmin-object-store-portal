import logging
import sys
import traceback

import yaml
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware import Middleware, httpsredirect, sessions
from starsessions import SessionAutoloadMiddleware, SessionMiddleware
from starsessions.stores.redis import RedisStore

from objectstore_interface.custom_middleware import (
    MockSessionMiddleware,
    RedirectWhenLoggedOut,
    SessionValidationMiddleware,
)
from objectstore_interface.pages.access_key_pages import bucket, create, view
from objectstore_interface.pages.bucket_pages import create_bucket, policies
from objectstore_interface.pages.login_pages import login
from objectstore_interface.pages.object_store_pages import auth, list
from redis.asyncio import Redis


templates = Jinja2Templates(directory="objectstore_interface/templates")
with open("conf/common.secrets.yaml") as confile:
    config = yaml.safe_load(confile)

# Initialize Redis connection for session storage
redis_client = Redis.from_url(config["redis"]["connection"])
session_store = RedisStore(connection=redis_client)

# Configure middleware stack for the application
middleware = [
    Middleware(SessionMiddleware, store=session_store, lifetime=3600 * 24 * 14),
    Middleware(SessionAutoloadMiddleware),
    Middleware(RedirectWhenLoggedOut),
    Middleware(SessionValidationMiddleware),
]

# Add mock session middleware for testing environments
if config["testing"] == True:
    middleware.insert(1, Middleware(MockSessionMiddleware))

app = FastAPI(middleware=middleware)

app.mount(
    "/static", StaticFiles(directory="objectstore_interface/static"), name="static"
)

app.include_router(view.router)
app.include_router(create.router)
app.include_router(login.router)
app.include_router(auth.router)
app.include_router(list.router)
app.include_router(bucket.router)
app.include_router(create_bucket.router)
app.include_router(policies.router)


@app.get("/")
async def root(request: Request):
    """Serve the application's home page or return an error page if an exception occurs."""
    try:
        return templates.TemplateResponse(request, "index.html")
    except Exception as exc:

        logging.error("".join(traceback.format_exception(exc)))
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "error": "".join(traceback.format_exception(exc)),
                "advanced": True,
            },
        )
