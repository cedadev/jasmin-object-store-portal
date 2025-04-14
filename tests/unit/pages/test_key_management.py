import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from fastapi.testclient import TestClient

# Application imports
from objectstore_interface.pages.access_key_pages import create, view
from objectstore_interface.object_store_classes.datacore import DataCore
from objectstore_interface.main import app

# Test constants
TEST_STORE = "test-store"
TEST_ENDPOINT = "test-endpoint.s3.jc.rl.ac.uk"
TEST_AUTH_KEY = "test-key"
TEST_EXPIRES = "31/12/2023"
TEST_DESCRIPTION = "Test key"


# Test client setup
client = TestClient(app)


# Fixtures for common test data
@pytest.fixture
def test_datacore_json():
    """
    Return JSON representation of test DataCore configuration.

    This simulates the serialized DataCore object stored in session.
    """
    return json.dumps(
        {
            "type": "Datacore",
            "location": TEST_ENDPOINT,
            "auth_access_key": TEST_AUTH_KEY,
        }
    )


@pytest.fixture
def mock_request(test_datacore_json):
    """
    Create a mock request with session data.

    This fixture simulates a FastAPI request object with
    the necessary session data for authenticated operations.
    """
    request = MagicMock()
    request.session = {
        TEST_STORE: test_datacore_json,
        f"access_key_{TEST_STORE}": TEST_AUTH_KEY,
    }
    return request


@pytest.fixture
def mock_success_datacore():
    """
    Create a mock DataCore instance for successful operations.

    This fixture returns a mock with pre-configured success responses.
    """
    datacore = MagicMock(spec=DataCore)
    datacore.create_key.return_value = {
        "status_code": 201,
        "access_key": "new-access-key",
        "secret_key": "secret-key-value",
    }
    return datacore


@pytest.fixture
def mock_error_datacore():
    """
    Create a mock DataCore instance for error responses.

    This fixture returns a mock with pre-configured error responses.
    """
    datacore = MagicMock(spec=DataCore)
    datacore.create_key.return_value = {
        "status_code": 400,
        "error": "Error: Invalid parameters",
    }
    return datacore


@pytest.fixture
def mock_access_keys():
    """
    Create sample access keys for testing listing functionality.

    Returns keys with different statuses (active, expiring) for UI testing.
    """
    today = datetime.today().replace(tzinfo=timezone.utc)
    return [
        {
            "name": "test-active",
            "last_modified": today.strftime("%Y-%m-%d"),
            "lifepoint": (today + relativedelta(weeks=52)).strftime("%Y-%m-%d"),
            "lifepoint_date": today + relativedelta(weeks=52),
            "expiring": False,
            "expired": False,
            "description": "test-key",
        },
        {
            "name": "test-expiring",
            "last_modified": today.strftime("%Y-%m-%d"),
            "lifepoint": (today + relativedelta(days=5)).strftime("%Y-%m-%d"),
            "lifepoint_date": today + relativedelta(days=5),
            "expiring": True,
            "expired": False,
            "description": "test-expiry-key",
        },
        {
            "name": "test-expired",
            "last_modified": today.strftime("%Y-%m-%d"),
            "lifepoint": (today - relativedelta(days=1)).strftime("%Y-%m-%d"),
            "lifepoint_date": today - relativedelta(days=1),
            "expiring": False,
            "expired": True,
            "description": "test-expired-key",
        },
    ]


@pytest.mark.asyncio
@patch("objectstore_interface.object_store_classes.datacore.r")
async def test_create_key_success(
    mock_r, mock_request, test_datacore_json, mock_success_datacore
):
    """
    Test successful key creation with valid parameters.
    """
    # Configure mock API response
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.text = f"Token new-access-key issued for test in {TEST_ENDPOINT}"
    mock_r.post.return_value = mock_response

    # Mock the storefromjson function to inject our test mock
    with patch(
        "objectstore_interface.pages.access_key_pages.create.storefromjson"
    ) as mock_storefromjson:
        mock_storefromjson.return_value = mock_success_datacore

        # Call the key creation function
        response = await create.create_object_store_keys(
            request=mock_request,
            storename=TEST_STORE,
            expires=TEST_EXPIRES,
            description=TEST_DESCRIPTION,
        )

        # Response details
        assert response.status_code == 200
        assert "Successfully created Secret" in str(response.body)

        # Proper DataCore methods were called with expected parameters
        mock_storefromjson.assert_called_once_with(test_datacore_json)
        mock_success_datacore.create_key.assert_called_once()

        # Verify parameters passed to create_key
        call_args = mock_success_datacore.create_key.call_args
        assert TEST_DESCRIPTION in str(call_args)
        assert TEST_EXPIRES in str(call_args)


@pytest.mark.asyncio
@patch("objectstore_interface.object_store_classes.datacore.r")
async def test_create_key_error(
    mock_r, mock_request, test_datacore_json, mock_error_datacore
):
    """
    Test key creation with error response.
    """
    # Mock the storefromjson function to inject our error mock
    with patch(
        "objectstore_interface.pages.access_key_pages.create.storefromjson"
    ) as mock_storefromjson:
        mock_storefromjson.return_value = mock_error_datacore

        # Call with invalid parameters to trigger error
        response = await create.create_object_store_keys(
            request=mock_request,
            storename=TEST_STORE,
            expires="invalid-date",
            description=TEST_DESCRIPTION,
        )

        # Error handling
        assert response.status_code == 500
        assert "Oops! Something went wrong" in str(response.body)

        # Proper DataCore methods were called
        mock_storefromjson.assert_called_once_with(test_datacore_json)
        mock_error_datacore.create_key.assert_called_once()


@pytest.mark.asyncio
@patch("objectstore_interface.object_store_classes.datacore.r")
@patch("objectstore_interface.pages.access_key_pages.create.storefromjson")
@patch("objectstore_interface.pages.access_key_pages.create.logging")
@patch("objectstore_interface.pages.access_key_pages.create.traceback")
@patch(
    "objectstore_interface.pages.access_key_pages.create.templates"
)  # Add templates mock
async def test_create_key_exception(
    mock_templates,
    mock_traceback,
    mock_logging,
    mock_storefromjson,
    mock_request,
):
    """
    Test key creation when an exception occurs.
    """
    # Configure mocks to raise exception
    mock_store = MagicMock()
    mock_store.create_key.side_effect = Exception("Connection error")
    mock_storefromjson.return_value = mock_store
    mock_traceback.format_exception.return_value = ["Mocked traceback"]

    # Configure templates mock to return a response
    mock_response = MagicMock()
    mock_templates.TemplateResponse.return_value = mock_response

    # Call the function that will raise an exception
    response = await create.create_object_store_keys(
        request=mock_request,
        storename=TEST_STORE,
        expires=TEST_EXPIRES,
        description=TEST_DESCRIPTION,
    )

    # Error is logged properly
    mock_logging.error.assert_called_once()

    # Error page template is used
    mock_templates.TemplateResponse.assert_called_once()
    template_name = mock_templates.TemplateResponse.call_args[0][1]
    assert template_name == "error.html"

    # Error context contains expected information
    context = mock_templates.TemplateResponse.call_args[0][2]
    assert "error" in context
    assert "advanced" in context
    assert context["advanced"] == True


@pytest.mark.asyncio
@patch("objectstore_interface.object_store_classes.datacore.r")
async def test_delete_key_success(mock_r, mock_request):
    """
    Test successful key deletion.
    """
    # Mock API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_r.delete.return_value = mock_response

    # Mock DataCore for deletion
    with patch(
        "objectstore_interface.pages.access_key_pages.view.storefromjson"
    ) as mock_storefromjson:
        mock_datacore = MagicMock(spec=DataCore)
        mock_datacore.delete_key.return_value = {"status_code": 200}
        mock_storefromjson.return_value = mock_datacore

        # Delete an access key
        delete_key = "key-to-delete"
        response = await view.access_key_delete(
            request=mock_request,
            storename=TEST_STORE,
            delete_access_key=delete_key,
        )

        # Successful deletion and redirect
        assert response.status_code == 303
        assert f"/object-store/{TEST_STORE}/access-keys" in response.headers["location"]

        # DataCore deletion method was called with correct key
        mock_datacore.delete_key.assert_called_once_with(delete_key)


@pytest.mark.asyncio
@patch("objectstore_interface.object_store_classes.datacore.r")
async def test_list_keys(mock_r, mock_request, mock_access_keys):
    """
    Test listing access keys.
    """
    # Mock response for key listing
    with patch(
        "objectstore_interface.pages.access_key_pages.view.storefromjson"
    ) as mock_storefromjson:
        # Create mock DataCore with pre-defined key list
        mock_datacore = MagicMock(spec=DataCore)
        mock_datacore.get_store.return_value = {
            "status_code": 200,
            "access_keys": mock_access_keys,
        }
        mock_storefromjson.return_value = mock_datacore

        # Retrieve key listing
        response = await view.object_store_show_details(
            request=mock_request, storename=TEST_STORE
        )

        # Response structure
        assert response.status_code == 200
        mock_datacore.get_store.assert_called_once()

        # Keys are present in the response
        response_content = str(response.body)
        for key in mock_access_keys:
            assert key["name"] in response_content

        # Template is rendered correctly
        assert any(term in response_content for term in ["objectstore.html", "view"])


@pytest.mark.asyncio
@patch("objectstore_interface.object_store_classes.datacore.r")
@patch("objectstore_interface.pages.access_key_pages.view.storefromjson")
@patch("objectstore_interface.pages.access_key_pages.view.templates")
@patch("objectstore_interface.pages.access_key_pages.view.logging")
async def test_list_keys_api_error(
    mock_logging,
    mock_templates,
    mock_storefromjson,
    mock_r,
    mock_request,
):
    """
    Test listing keys when API returns an error.
    """
    # Configure mock with error response
    mock_datacore = MagicMock(spec=DataCore)
    mock_datacore.get_store.return_value = {
        "status_code": 500,
        "error": "API connection error",
    }
    mock_storefromjson.return_value = mock_datacore

    # Configure templates mock to return a response object
    mock_response = MagicMock()
    mock_response.status_code = 200  # The template response has a 200 status
    mock_templates.TemplateResponse.return_value = mock_response

    # Attempt to list keys with API error
    response = await view.object_store_show_details(
        request=mock_request, storename=TEST_STORE
    )

    # Verify the DataCore method was called
    mock_datacore.get_store.assert_called_once()

    # Verify error was logged
    mock_logging.error.assert_called_once()

    # Verify template was rendered instead of redirect
    mock_templates.TemplateResponse.assert_called_once()

    # Check that the error template was used
    template_name = mock_templates.TemplateResponse.call_args[0][1]
    assert template_name == "error.html"

    # Verify the error context includes necessary information
    context = mock_templates.TemplateResponse.call_args[0][2]
    assert "error" in context

    # Verify the response is the template response
    assert response == mock_response


@pytest.mark.asyncio
@patch("objectstore_interface.object_store_classes.datacore.r")
async def test_expired_keys_display(mock_r, mock_request, mock_access_keys):
    """
    Test expired keys display correctly in the listing.
    """
    with patch(
        "objectstore_interface.pages.access_key_pages.view.storefromjson"
    ) as mock_storefromjson:
        # Create mock DataCore with keys including expired one
        mock_datacore = MagicMock(spec=DataCore)
        # Make sure we have an expired key in the list
        mock_datacore.get_store.return_value = {
            "status_code": 200,
            "access_keys": mock_access_keys,
        }
        mock_storefromjson.return_value = mock_datacore

        # Retrieve key listing
        response = await view.object_store_show_details(
            request=mock_request, storename=TEST_STORE
        )

        # Response contains expired key formatting
        response_content = str(response.body)
        # Check for expired key indicator in the response
        assert "test-expired" in response_content
        assert "EXPIRED" in response_content
        # Check for the danger class that's applied to expired keys
        assert "text-danger" in response_content
        # Check for the disabled attribute on delete button for expired keys
        assert "disabled" in response_content
