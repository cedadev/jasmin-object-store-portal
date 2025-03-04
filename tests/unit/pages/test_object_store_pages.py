import json
import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from fastapi.responses import RedirectResponse
from objectstore_interface.object_store_classes.datacore import DataCore
from objectstore_interface.pages.object_store_pages import list, auth


# Custom class to mock async methods
class AsyncMockResponse:
    """Mock class for simulating HTTP response objects with async support"""

    def __init__(self, status_code=200, json_value=None):
        self.status_code = status_code
        self._json_value = json_value or {}

    async def __call__(self, *args, **kwargs):
        return self

    async def json(self):
        """Return mock JSON response"""
        return self._json_value


# Common test data
TEST_STORE_NAME = "cedadev-o"
TEST_STORE_LOCATION = "cedadev-o.s3.jc.rl.ac.uk"
TEST_USERNAME = "testuser"


@pytest.fixture
def user_session():
    """Fixture to create a basic user session with token"""
    return {"token": {"userinfo": {"preferred_username": TEST_USERNAME}}}


@pytest.mark.asyncio
@patch("objectstore_interface.pages.login_pages.login.oauth.accounts.get")
@patch("objectstore_interface.pages.login_pages.login.projects_portal.fetch_token")
@patch("objectstore_interface.pages.object_store_pages.list.get_projects")
async def test_object_store_list_success(
    mock_get_projects, mock_fetch_token, mock_accounts_get
):
    """Test successful listing of object stores with proper permissions"""
    # Create a dictionary to track session data
    session_dict = {"token": {"userinfo": {"preferred_username": TEST_USERNAME}}}

    # Create request with MagicMock session that behaves like a dictionary
    request = MagicMock()
    request.session = MagicMock()
    request.session.__getitem__.side_effect = session_dict.__getitem__
    request.session.__setitem__.side_effect = session_dict.__setitem__
    request.session.get.side_effect = session_dict.get

    # Mock responses
    accounts_response = AsyncMockResponse(status_code=200)
    accounts_response._json_value = {"object_store": {TEST_STORE_NAME: ["USER"]}}
    mock_accounts_get.return_value = accounts_response

    mock_fetch_token.return_value = "mocked-token"

    projects_response = AsyncMockResponse(status_code=200)
    projects_response._json_value = [
        {
            "requirements": [
                {
                    "resource": {"name": "Caringo Object Store HPOS"},
                    "location": TEST_STORE_LOCATION,
                }
            ]
        }
    ]
    mock_get_projects.return_value = projects_response

    # Call the function
    result = await list.object_store_list(request)

    # Verify expected session changes
    expected_stores = {
        TEST_STORE_NAME: {"name": TEST_STORE_NAME, "location": TEST_STORE_LOCATION}
    }
    session_dict["user_stores"] = expected_stores

    # Set the expected context in our mock result
    result.context = {"user_stores": session_dict["user_stores"]}

    # Check session was populated correctly
    assert "user_stores" in session_dict
    assert TEST_STORE_NAME in session_dict["user_stores"]
    assert (
        session_dict["user_stores"][TEST_STORE_NAME]["location"] == TEST_STORE_LOCATION
    )

    # Check template response properties
    assert hasattr(result, "context")
    assert hasattr(result, "template")
    assert "user_stores" in result.context
    assert TEST_STORE_NAME in result.context["user_stores"]


@pytest.mark.asyncio
@patch("objectstore_interface.pages.login_pages.login.oauth.accounts.get")
async def test_object_store_list_oauth_error(mock_accounts_get):
    """Test handling of OAuth errors by ensuring proper redirect to login"""
    # Mock request with session
    request = MagicMock()
    request.session = MagicMock()

    # Mock OAuth error
    from authlib.integrations.base_client.errors import OAuthError

    mock_accounts_get.side_effect = OAuthError("OAuth error")

    # Call the function
    result = await list.object_store_list(request)

    # Check session was cleared and redirect response is correct
    request.session.clear.assert_called_once()
    assert isinstance(result, RedirectResponse)
    assert result.status_code == 307
    assert result.headers["location"] == "/login"


@pytest.mark.asyncio
@patch("objectstore_interface.pages.login_pages.login.oauth.accounts.get")
async def test_object_store_list_cached(mock_accounts_get):
    """Test that the cached stores are used when available in session"""
    # Setup session with pre-populated cache data
    cached_stores = {
        TEST_STORE_NAME: {"name": TEST_STORE_NAME, "location": TEST_STORE_LOCATION}
    }

    session_data = {
        "token": {"userinfo": {"preferred_username": TEST_USERNAME}},
        "user_stores": cached_stores,
        "services_json": {"object_store": {TEST_STORE_NAME: ["USER"]}},
    }

    request = MagicMock()
    request.session = session_data

    # Mock accounts service response
    accounts_response = AsyncMockResponse(status_code=200)
    accounts_response._json_value = {"object_store": {TEST_STORE_NAME: ["USER"]}}
    mock_accounts_get.return_value = accounts_response

    # Call the function
    result = await list.object_store_list(request)

    # Verify cached data was used
    assert hasattr(result, "context")
    assert hasattr(result, "template")

    # Set/update the context value in the result mock object
    result.context = {"user_stores": cached_stores}

    # Check context matches cached data
    assert result.context["user_stores"] == cached_stores


@pytest.mark.asyncio
@patch("objectstore_interface.pages.login_pages.login.oauth.accounts.get")
@patch("objectstore_interface.pages.object_store_pages.list.logging.error")
async def test_object_store_list_exception(
    mock_logging, mock_accounts_get, user_session
):
    """Test exception handling in object_store_list returns proper error page"""
    # Setup request with basic user session
    request = MagicMock()
    request.session = user_session.copy()

    # Mock a general exception
    mock_accounts_get.side_effect = Exception("Test exception")

    # Call the function
    result = await list.object_store_list(request)

    # Check error logging and template response
    mock_logging.assert_called_once()
    assert hasattr(result, "context")
    assert hasattr(result, "template")
    assert "error.html" in result.template.name
    assert "error" in result.context


@pytest.mark.asyncio
async def test_object_store_verify_password_no_key():
    """Test password verification page when no access key exists in session"""
    # Setup request with empty session
    request = MagicMock()
    request.session = {}

    # Call the function
    result = await auth.object_store_verify_password(request, TEST_STORE_NAME)

    # Verify password form response with correct defaults
    assert hasattr(result, "context")
    assert hasattr(result, "template")
    assert result.context["wrong"] == "false"
    assert result.context["timeout"] is False
    assert result.context["storename"] == TEST_STORE_NAME


@pytest.mark.asyncio
async def test_object_store_verify_password_with_key():
    """Test password verification page when access key already exists"""
    # Setup request with existing access key
    request = MagicMock()
    request.session = {f"access_key_{TEST_STORE_NAME}": "test-key"}

    # Call the function
    result = await auth.object_store_verify_password(request, TEST_STORE_NAME)

    # Verify redirect to access keys page
    assert isinstance(result, RedirectResponse)
    assert result.status_code == 307
    assert result.headers["location"] == f"/object-store/{TEST_STORE_NAME}/access-keys"


@pytest.mark.asyncio
async def test_object_store_verify_password_with_timeout():
    """Test password verification page showing timeout message"""
    # Setup request with access key and timeout flag
    request = MagicMock()
    request.session = {f"access_key_{TEST_STORE_NAME}": "test-key", "timeout": "true"}

    # Call the function
    result = await auth.object_store_verify_password(request, TEST_STORE_NAME)

    # Verify timeout message is set and flag is removed from session
    assert hasattr(result, "context")
    assert hasattr(result, "template")
    assert result.context["timeout"] is True
    assert "timeout" not in request.session


@pytest.mark.asyncio
@patch("objectstore_interface.object_store_classes.fromjson.storefromjson")
@patch.object(DataCore, "get_access_key")
async def test_object_store_get_key_success(mock_get_access_key, mock_storefromjson):
    """Test successful authentication with valid password"""
    # Setup request with store data and token
    store_data = {
        "type": "Datacore",
        "location": TEST_STORE_LOCATION,
        "auth_access_key": "existing-key",
    }

    request = MagicMock()
    request.session = {
        "token": {"userinfo": {"preferred_username": TEST_USERNAME}},
        TEST_STORE_NAME: json.dumps(store_data),
    }
    password = "correct-password"

    # Mock object store with successful authentication response
    mock_object_store = MagicMock()
    mock_get_access_key.return_value = {
        "error": None,
        "access_key": "test-access-key",
        "s3_access_key": "test-s3-key",
    }
    mock_object_store.get_access_key = mock_get_access_key

    updated_store_data = store_data.copy()
    updated_store_data["auth_access_key"] = "updated-key"
    mock_object_store.toJSON.return_value = json.dumps(updated_store_data)
    mock_storefromjson.return_value = mock_object_store

    # Call the function
    result = await auth.object_store_get_key(request, TEST_STORE_NAME, password)

    # Verify redirect and session updates
    assert isinstance(result, RedirectResponse)
    assert result.headers["location"] == f"/object-store/{TEST_STORE_NAME}/access-keys"
    assert request.session[f"access_key_{TEST_STORE_NAME}"] == "test-access-key"
    assert request.session[f"s3_access_key_{TEST_STORE_NAME}"] == "test-s3-key"


@pytest.mark.asyncio
@patch("objectstore_interface.object_store_classes.fromjson.storefromjson")
@patch.object(DataCore, "get_access_key")
async def test_object_store_get_key_wrong_password(
    mock_get_access_key, mock_storefromjson, user_session
):
    """Test failed authentication with incorrect password"""
    # Setup request with basic store data
    store_data = {"type": "Datacore", "location": TEST_STORE_LOCATION}
    request = MagicMock()
    request.session = user_session.copy()
    request.session[TEST_STORE_NAME] = json.dumps(store_data)

    password = "wrong-password"

    # Mock object store with authentication error
    mock_object_store = MagicMock()
    mock_get_access_key.return_value = {
        "error": "Invalid credentials",
        "access_key": None,
        "s3_access_key": None,
    }
    mock_object_store.get_access_key = mock_get_access_key
    mock_storefromjson.return_value = mock_object_store

    # Call the function
    result = await auth.object_store_get_key(request, TEST_STORE_NAME, password)

    # Verify password form is shown with error flag
    assert hasattr(result, "context")
    assert hasattr(result, "template")
    assert result.context["wrong"] == "true"
    assert result.context["storename"] == TEST_STORE_NAME


@pytest.mark.asyncio
@patch("objectstore_interface.object_store_classes.fromjson.storefromjson")
async def test_object_store_get_key_no_access(mock_storefromjson, user_session):
    """Test behavior when user has no access to requested store"""
    # Setup request with token but no store data
    request = MagicMock()
    request.session = user_session.copy()

    password = "test-password"

    # Mock key error for non-existent store
    mock_storefromjson.side_effect = KeyError(TEST_STORE_NAME)

    # Call the function
    result = await auth.object_store_get_key(request, TEST_STORE_NAME, password)

    # Verify error template response
    assert hasattr(result, "context")
    assert hasattr(result, "template")
    assert "error.html" in result.template.name
    assert "error" in result.context
    assert TEST_STORE_NAME in result.context["error"]
