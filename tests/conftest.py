import pytest
from objectstore_interface.pages.access_key_pages import view, create
from objectstore_interface.pages.login_pages import login
from objectstore_interface.pages.object_store_pages import auth, list
from unittest.mock import MagicMock, patch
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.config import Config
from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

config = Config("tests/.env")

@pytest.fixture
def mocked_session_client(request):

    token = config("token")

    
    app = FastAPI()

    app.mount("/static", StaticFiles(directory="objectstore_interface/static"), name="static")

    app.include_router(view.router)
    app.include_router(create.router)
    app.include_router(login.router)
    app.include_router(auth.router)
    app.include_router(list.router)
    
    client = TestClient(app)

    client.token = token
    yield client
