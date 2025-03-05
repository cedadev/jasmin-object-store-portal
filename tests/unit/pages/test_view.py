import pytest
from unittest.mock import patch, MagicMock
import json
from fastapi.testclient import TestClient
from fastapi import status
from starlette.responses import RedirectResponse

from objectstore_interface.pages.access_key_pages import view
from objectstore_interface.main import app
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta


# Define AsyncMock for mocking awaitable methods
class AsyncMock(MagicMock):
    """Custom mock class for mocking awaitable methods."""

    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


# Test client setup
@pytest.fixture
def client():
    """Return a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_request():
    """Create a mock request with valid session data for testing.

    Returns:
        MagicMock: A mock request object with pre-configured session data
    """
    request = MagicMock()
    request.session = {
        "test-store": json.dumps(
            {
                "type": "Datacore",
                "location": "test-endpoint.s3.jc.rl.ac.uk",
                "auth_access_key": "test-key",
            }
        ),
        "access_key_test-store": "test-key",
    }
    return request


@pytest.fixture
def access_key_data():
    """Provides sample access key data for testing."""
    return {
        "name": "test-key",
        "description": "Test key",
        "created": datetime.now(timezone.utc).isoformat(),
        "expires": (datetime.now(timezone.utc) + relativedelta(weeks=52)).isoformat(),
    }


class TestObjectStoreViewDetails:
    """Test suite for object store view details page functionality."""

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    async def test_view_key_list_success(self, mock_r, mock_request, access_key_data):
        """Test successful retrieval and display of access keys.

        Verifies that when a valid request is made, the access keys are
        correctly retrieved and rendered in the response template.
        """
        # Mock the store from json function and configure successful API response
        with patch(
            "objectstore_interface.pages.access_key_pages.view.storefromjson"
        ) as mock_storefromjson:
            mock_datacore = MagicMock()
            # Configure mock to return successful API response with test access key data
            mock_datacore.get_store = AsyncMock(
                return_value={
                    "status_code": status.HTTP_200_OK,
                    "access_keys": [access_key_data],
                }
            )
            mock_storefromjson.return_value = mock_datacore

            # Call the function under test with our mock request
            response = await view.object_store_show_details(
                request=mock_request, storename="test-store"
            )

            # Verify the response contains the expected template and status code
            assert response.status_code == status.HTTP_200_OK
            assert hasattr(response, "template")
            # Fix: Check the template name property instead of treating template as iterable
            assert response.template.name == "access_key_pages/objectstore.html"

            # Verify the template context contains the expected access key data
            assert hasattr(response, "context")
            assert "access_keys" in response.context
            assert "storename" in response.context
            assert response.context["storename"] == "test-store"
            assert response.context["view"] == "view"
            assert len(response.context["access_keys"]) == 1
            assert response.context["access_keys"][0]["name"] == "test-key"

            # Sanity check for expected content in response body
            assert "test-key" in str(response.body)

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    async def test_view_key_list_unauthorized(self, mock_r, mock_request):
        """Test behavior when access key is expired or unauthorized.

        Verifies proper redirect to authentication page when the access key
        is invalid or has expired.
        """
        # Mock the store from json function and configure unauthorized API response
        with patch(
            "objectstore_interface.pages.access_key_pages.view.storefromjson"
        ) as mock_storefromjson:
            mock_datacore = MagicMock()
            # Configure mock to return unauthorized response
            mock_datacore.get_store = AsyncMock(
                return_value={"status_code": status.HTTP_401_UNAUTHORIZED}
            )
            mock_storefromjson.return_value = mock_datacore

            # Call the function under test with unauthorized credentials
            response = await view.object_store_show_details(
                request=mock_request, storename="test-store"
            )

            # Verify response redirects to authentication page and session is cleared
            assert isinstance(response, RedirectResponse)
            assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
            assert response.headers["location"] == "/object-store/test-store"
            assert "access_key_test-store" not in mock_request.session

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    @patch("objectstore_interface.pages.access_key_pages.view.storefromjson")
    @patch("objectstore_interface.pages.access_key_pages.view.templates")
    async def test_view_key_list_error(
        self, mock_templates, mock_storefromjson, mock_r, mock_request
    ):
        """Test handling of API errors when retrieving key list.

        Verifies that errors from the store API are properly displayed
        to the user with appropriate status codes.
        """
        # Create a response object with attributes rather than a dictionary
        # since the view function expects object attributes
        mock_response = MagicMock()
        mock_response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_response.text = "Internal server error"

        mock_datacore = MagicMock()
        mock_datacore.get_store = AsyncMock(return_value=mock_response)
        mock_storefromjson.return_value = mock_datacore

        # Set up template response mock with necessary properties
        mock_template_response = MagicMock(status_code=200)
        mock_templates.TemplateResponse.return_value = mock_template_response

        # Call the function under test with configured mocks that trigger error handling
        await view.object_store_show_details(
            request=mock_request, storename="test-store"
        )

        # Verify error template was rendered with correct error message
        mock_templates.TemplateResponse.assert_called_once()

        # Inspect the positional arguments passed to TemplateResponse
        call_args = mock_templates.TemplateResponse.call_args[0]

        # First argument should be the template name
        assert "error.html" == call_args[1]

        # Second argument should be the context dictionary
        context = call_args[2]
        assert "error" in context
        assert "500: Internal server error" in context["error"]

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    @patch("objectstore_interface.pages.access_key_pages.view.storefromjson")
    @patch("objectstore_interface.pages.access_key_pages.view.logging")
    async def test_view_key_list_exception(
        self, mock_logging, mock_storefromjson, mock_r, mock_request
    ):
        """Test handling of exceptions during key list retrieval.

        Verifies that unexpected exceptions are properly logged and
        an appropriate error page is shown to the user.
        """
        # Configure mock to throw an exception when called
        mock_storefromjson.side_effect = Exception("Unexpected error")

        # Call the function under test which should trigger exception handling
        response = await view.object_store_show_details(
            request=mock_request, storename="test-store"
        )

        # Verify exception was logged and error template displayed
        mock_logging.error.assert_called_once()
        assert hasattr(response, "template")
        assert response.template.name == "error.html"
        assert hasattr(response, "context")
        assert "error" in response.context
        assert "advanced" in response.context
        assert response.context["advanced"] is True
