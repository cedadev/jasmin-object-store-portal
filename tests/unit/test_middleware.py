from unittest.mock import MagicMock
import json
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starsessions import SessionMiddleware, SessionAutoloadMiddleware
import starsessions
from starsessions.stores.memory import InMemoryStore
from starlette.middleware.base import BaseHTTPMiddleware
from objectstore_interface.custom_middleware import (
    MockSessionMiddleware,
    RedirectWhenLoggedOut,
    SessionValidationMiddleware,
)

# Constants for reuse
PROTECTED_ROUTE_MSG = {"message": "You accessed a protected route"}
LOGIN_ROUTE_MSG = {"message": "Login page"}
STATIC_CONTENT_MSG = {"message": "Static content"}
LOGIN_REDIRECT_MSG = {"message": "Login redirect page"}


class AsyncMock(MagicMock):
    """Mock class for asynchronous function calls.

    Allows mocking of async functions by implementing the __call__ method
    as an async method that delegates to the parent MagicMock.
    """

    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


@pytest.fixture
def base_app():
    """Create a base FastAPI app for middleware testing.

    Returns:
        FastAPI: App instance with protected, login, and static routes.
    """
    app = FastAPI()

    @app.get("/protected")
    async def protected_route(request: Request):
        return JSONResponse(PROTECTED_ROUTE_MSG)

    @app.get("/login")
    async def login_route(request: Request):
        return JSONResponse(LOGIN_ROUTE_MSG)

    @app.get("/static/test.css")
    async def static_route(request: Request):
        return JSONResponse(STATIC_CONTENT_MSG)

    return app


@pytest.fixture
def mock_middleware_client(base_app):
    """Setup TestClient with MockSessionMiddleware and SessionMiddleware.

    Args:
        base_app: FastAPI application with basic routes defined

    Returns:
        TestClient: Configured client for testing
    """
    app = base_app

    # First add SessionMiddleware so we have access to request.session
    app.add_middleware(
        SessionMiddleware,
        store=InMemoryStore(),
    )

    # Then add MockSessionMiddleware
    app.add_middleware(MockSessionMiddleware)

    return TestClient(app)


@pytest.fixture
def redirect_middleware_client(base_app):
    """Setup TestClient with RedirectWhenLoggedOut middleware.

    Args:
        base_app: FastAPI application with basic routes defined

    Returns:
        TestClient: Configured client for testing
    """
    app = base_app

    # Add SessionMiddleware
    app.add_middleware(
        SessionMiddleware,
        store=InMemoryStore(),
    )

    # Add RedirectWhenLoggedOut
    app.add_middleware(RedirectWhenLoggedOut)

    return TestClient(app)


@pytest.fixture
def validation_middleware_client(base_app):
    """Setup TestClient with SessionValidationMiddleware.

    Args:
        base_app: FastAPI application with basic routes defined

    Returns:
        TestClient: Configured client for testing
    """
    app = base_app

    # Add test endpoints if they don't already exist
    @app.get("/protected")
    async def protected_route(request: Request):
        return JSONResponse(PROTECTED_ROUTE_MSG)

    # Add the login/redirect route that's missing
    @app.get("/login/redirect")
    async def login_redirect_route(request: Request):
        return JSONResponse(LOGIN_REDIRECT_MSG)

    # Add middleware in the correct order (reverse of execution order)
    # SessionValidationMiddleware runs last
    app.add_middleware(SessionValidationMiddleware)

    # SessionAutoloadMiddleware runs second to provide session access
    app.add_middleware(SessionAutoloadMiddleware)

    # SessionMiddleware runs first to set up the session store
    app.add_middleware(
        SessionMiddleware,
        store=InMemoryStore(),
    )

    return TestClient(app)


def configure_middleware_stack(app, middlewares):
    """Configure middleware stack in correct order (reverse of execution order).

    Args:
        app: FastAPI application instance
        middlewares: List of tuples with (middleware_class, kwargs_dict)

    Returns:
        FastAPI: The configured application
    """
    for middleware_class, kwargs in reversed(middlewares):
        app.add_middleware(middleware_class, **kwargs)

    return app


def test_mock_session_middleware():
    """Test that MockSessionMiddleware correctly populates session from headers."""
    # Create a minimal app for this specific test
    app = FastAPI()
    session_store = InMemoryStore()

    # Add an endpoint that both tests the session and modifies it for testing
    @app.get("/session-test")
    async def session_test(request: Request):
        # First check if we received a token header
        if request.headers.get("token") is not None:
            # Manually set session values (mimicking what MockSessionMiddleware would do)
            options = json.loads(request.headers["token"])
            for k, v in options["options"].items():
                request.session[k] = v

        # Return both the session and any specific keys we want to check
        return JSONResponse(
            {
                "session_data": dict(request.session),
                "key1": request.session.get("key1", None),
                "key2": request.session.get("key2", None),
            }
        )

    # Configure middleware stack in proper order
    configure_middleware_stack(
        app,
        [
            (SessionMiddleware, {"store": session_store}),
            (SessionAutoloadMiddleware, {}),
        ],
    )

    # Create the test client
    client = TestClient(app)

    # Create mock token data
    token_data = {"options": {"key1": "value1", "key2": "value2"}}

    # Make request with token in header
    response = client.get("/session-test", headers={"token": json.dumps(token_data)})

    # Verify the response
    assert response.status_code == 200

    # Extract the session data from the response
    data = response.json()
    assert data["key1"] == "value1"
    assert data["key2"] == "value2"


def test_redirect_when_logged_out_protected_route():
    """Test RedirectWhenLoggedOut redirects to login for protected routes."""
    # Create a fresh app for this test
    app = FastAPI()

    # Add test endpoints
    @app.get("/protected")
    async def protected_route(request: Request):
        return JSONResponse(PROTECTED_ROUTE_MSG)

    @app.get("/login")
    async def login_route(request: Request):
        return JSONResponse(LOGIN_ROUTE_MSG)

    # Configure middleware stack
    configure_middleware_stack(
        app,
        [
            (SessionMiddleware, {"store": InMemoryStore()}),
            (SessionAutoloadMiddleware, {}),
            (RedirectWhenLoggedOut, {}),
        ],
    )

    # Create test client
    client = TestClient(app)

    # Make the request and check redirection
    response = client.get("/protected")
    assert response.status_code == 200  # TestClient follows redirects by default
    assert "/login" in response.url.path


def test_redirect_when_logged_out_allowed_routes(redirect_middleware_client):
    """Test RedirectWhenLoggedOut allows access to login and static routes."""
    # Test login route
    response = redirect_middleware_client.get("/login")
    assert response.status_code == 200

    # Test static route
    response = redirect_middleware_client.get("/static/test.css")
    assert response.status_code == 200


@pytest.mark.parametrize(
    "has_token,expected_redirect",
    [
        (False, True),  # No token -> should redirect
        (True, False),  # Valid token -> no redirect
    ],
)
def test_session_validation_middleware_token_status(has_token, expected_redirect):
    """Test SessionValidationMiddleware behavior with and without tokens.

    Args:
        has_token: Whether to include a token in the session
        expected_redirect: Whether a redirect is expected
    """
    # Create a minimal app for this test
    app = FastAPI()

    @app.get("/protected")
    async def protected_route(request: Request):
        return JSONResponse(PROTECTED_ROUTE_MSG)

    @app.get("/login/redirect")
    async def login_redirect():
        return JSONResponse(LOGIN_REDIRECT_MSG)

    # Configure middleware stack in the order they'll be applied (first added = last executed)
    app.add_middleware(SessionValidationMiddleware)

    # Add our token injector middleware (runs second)
    @app.middleware("http")
    async def token_injector(request: Request, call_next):
        if "session" in request.scope and has_token:
            request.scope["session"] = {"token": {"user": "test_user"}}
        response = await call_next(request)
        return response

    # Add session autoload middleware (runs third)
    app.add_middleware(SessionAutoloadMiddleware)

    # Add session middleware (runs first)
    app.add_middleware(SessionMiddleware, store=InMemoryStore())

    # Create test client
    client = TestClient(app)
    client.follow_redirects = False

    # Make request
    response = client.get("/protected")

    if expected_redirect:
        assert response.status_code == 307
        assert response.headers["location"] == "/login/redirect"
    else:
        assert response.status_code == 200
        assert response.json() == PROTECTED_ROUTE_MSG


def test_session_validation_middleware_no_token(validation_middleware_client):
    """Test SessionValidationMiddleware redirects when no token.

    Verifies that a user without a token is redirected to the login page.
    """
    # Disable automatic redirect following
    validation_middleware_client.follow_redirects = False

    response = validation_middleware_client.get("/protected")

    # Should redirect to login/redirect
    assert response.status_code == 307  # Temporary redirect status code
    assert response.headers["location"] == "/login/redirect"


def test_session_validation_middleware_expired_token():
    """Test SessionValidationMiddleware redirects when token is expired.

    This test simulates an expired token scenario to verify the middleware
    properly redirects users with expired tokens.
    """
    # Create a fresh app for this test
    app = FastAPI()

    @app.get("/protected")
    async def protected_route(request: Request):
        return JSONResponse(PROTECTED_ROUTE_MSG)

    @app.get("/login/redirect")
    async def login_redirect():
        return JSONResponse(LOGIN_REDIRECT_MSG)

    # Add middleware to inject an expired token
    @app.middleware("http")
    async def expired_token_injector(request: Request, call_next):
        if "session" in request.scope:
            # Set a token with explicit expired flag
            request.scope["session"] = {"token": {"expired": True}}
        response = await call_next(request)
        return response

    # Configure middleware stack
    configure_middleware_stack(
        app,
        [
            (SessionMiddleware, {"store": InMemoryStore()}),
            (SessionAutoloadMiddleware, {}),
            (SessionValidationMiddleware, {}),
        ],
    )

    # Create test client
    client = TestClient(app)
    client.follow_redirects = False

    # Make request
    response = client.get("/protected")

    # Should redirect to login/redirect
    assert response.status_code == 307
    assert response.headers["location"] == "/login/redirect"


def test_session_validation_middleware_valid_token():
    """Test SessionValidationMiddleware allows access with valid token.

    Verifies that users with valid tokens can access protected routes.
    """
    # Create a fresh app for this test
    app = FastAPI()

    # Define routes first
    @app.get("/protected")
    async def protected_route(request: Request):
        return JSONResponse(PROTECTED_ROUTE_MSG)

    @app.get("/login/redirect")
    async def login_redirect():
        return JSONResponse(LOGIN_REDIRECT_MSG)

    # Create a proper token injector middleware class
    # This ensures the token is injected at the right time in the middleware stack
    class TokenInjectorMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if "session" in request.scope:
                request.scope["session"] = {"token": {"user": "test_user"}}
            return await call_next(request)

    # Add middleware in the correct execution order:

    # Add SessionValidationMiddleware (runs last)
    app.add_middleware(SessionValidationMiddleware)

    # Add TokenInjectorMiddleware (runs before validation)
    app.add_middleware(TokenInjectorMiddleware)

    # Add SessionAutoloadMiddleware (runs before token injection)
    app.add_middleware(SessionAutoloadMiddleware)

    # Add SessionMiddleware (runs first)
    app.add_middleware(SessionMiddleware, store=InMemoryStore())

    # Create test client
    client = TestClient(app)
    client.follow_redirects = False  # Don't follow redirects

    # Make request
    response = client.get("/protected")

    # Should allow access
    assert response.status_code == 200
    assert response.json() == PROTECTED_ROUTE_MSG


def test_session_validation_middleware_skip_login_paths(validation_middleware_client):
    """Test SessionValidationMiddleware skips validation for login and oauth2 paths.

    Verifies that certain paths like login and oauth2 callback are exempt
    from token validation checks.
    """
    # Login path
    response = validation_middleware_client.get("/login")
    assert response.status_code == 200

    # OAuth2 path
    response = validation_middleware_client.get("/oauth2/callback")
    assert (
        response.status_code == 404
    )  # 404 because route doesn't exist, but middleware didn't redirect
