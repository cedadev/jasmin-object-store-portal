import json
from typing import Any, Dict, List
import pytest
import yaml
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta
from unittest.mock import PropertyMock, patch, MagicMock, AsyncMock

from tests.integration.test_api_endpoints import authenticate_with_store

# Constants for HTTP status codes
HTTP_OK = 200
HTTP_REDIRECT = 307
HTTP_POST_REDIRECT = 303

# Test data
TEST_KEY_DESCRIPTION = "Integration Test Key"


@pytest.fixture
def mock_create_key_response() -> Dict[str, Any]:
    """Mock successful key creation response.

    Returns:
        Dict containing a successful API response for key creation
    """
    return {
        "status_code": 201,
        "access_key": "test-integration-access-key",
        "secret_key": "test-integration-secret-key",
    }


@pytest.fixture
def config() -> Dict[str, Any]:
    """Load test configuration from YAML file.

    Returns:
        Dict containing test configuration values
    """
    config_path = "tests/integration/test_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def store_name(config: Dict[str, Any]) -> str:
    """Get store name from config.

    Returns:
        String with test store name
    """
    return config["test_store"]


@pytest.fixture
def mock_key_data() -> List[Dict[str, Any]]:
    """Generate mock key data for testing.

    Returns:
        List containing a mock access key record
    """
    today = datetime.now()
    return [
        {
            "name": "test-integration-key",
            "last_modified": today.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lifepoint": (today + relativedelta(weeks=4)).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            ),
            "lifepoint_date": today + relativedelta(weeks=4),
            "x_custom_meta_source": TEST_KEY_DESCRIPTION,
            "expiring": False,
            "expired": False,
        }
    ]


def test_access_key_lifecycle(
    test_client,
    auth_headers,
    config,
    store_name,
    mock_create_key_response,
    mock_key_data,
):
    """Test the complete lifecycle of an access key.

    This test covers:
    - Viewing the create key form
    - Creating a new access key
    - Viewing the key in the access key list
    - Deleting the key

    All steps should complete successfully to verify the full lifecycle works.
    """
    # Step 1: Authenticate with the store
    authenticate_with_store(test_client, auth_headers, store_name, config)

    # Define async functions for our mocks with proper signatures
    async def mock_get_store(request=None):
        """Handle get_store calls with proper signature"""
        return {
            "status_code": 200,
            "access_keys": mock_key_data,
        }

    async def mock_create_key_func(description, expires):
        """Handle create_key calls with proper signature"""
        return mock_create_key_response

    async def mock_delete_key(key_name):
        """Handle delete_key calls with proper signature"""
        return {"status_code": 200}

    # Set up patching for all necessary components
    with patch(
        "objectstore_interface.pages.access_key_pages.create.storefromjson"
    ) as mock_create_storefromjson, patch(
        "objectstore_interface.pages.access_key_pages.view.storefromjson"
    ) as mock_view_storefromjson, patch(
        "starlette.requests.Request.session", new_callable=PropertyMock
    ) as mock_session:
        # Create a mock store with correctly defined methods
        mock_store = MagicMock()
        mock_store.get_store = AsyncMock(side_effect=mock_get_store)
        mock_store.create_key = AsyncMock(side_effect=mock_create_key_func)
        mock_store.delete_key = AsyncMock(side_effect=mock_delete_key)

        # Configure toJSON to return a proper JSON string
        mock_store.toJSON.return_value = json.dumps(
            {
                "type": "DataCore",
                "location": f"{store_name}.s3.jc.rl.ac.uk",
                "auth_access_key": "test-key",
            }
        )

        # Set up both patch targets to use the same mock
        mock_create_storefromjson.return_value = mock_store
        mock_view_storefromjson.return_value = mock_store

        # Configure the mock session
        session_dict = {
            store_name: mock_store.toJSON(),
            f"access_key_{store_name}": "test-key",
            "token": auth_headers["token"],
        }
        mock_session.return_value = session_dict

        # Step 2: Access the create key form page
        create_form_response = test_client.get(
            f"/object-store/{store_name}/create-keys", headers=auth_headers
        )
        assert create_form_response.status_code == HTTP_OK

        # Step 3: Submit the form to create a new key
        expires_date = (datetime.now() + relativedelta(weeks=4)).strftime("%Y-%m-%d")
        create_key_response = test_client.post(
            f"/object-store/{store_name}/create-keys",
            headers=auth_headers,
            data={"description": TEST_KEY_DESCRIPTION, "expires": expires_date},
        )

        # Verify key creation response
        assert create_key_response.status_code == HTTP_OK
        content = BeautifulSoup(create_key_response.text, features="html.parser")

        # Check if key creation shows the expected details
        assert (
            content.find(
                string=lambda s: "test-integration-access-key" in s if s else False
            )
            is not None
        )
        assert (
            content.find(
                string=lambda s: "test-integration-secret-key" in s if s else False
            )
            is not None
        )

        # Verify the store's create_key method was called with expected parameters
        mock_store.create_key.assert_called_once()
        call_args = mock_store.create_key.call_args[0]
        assert TEST_KEY_DESCRIPTION in str(call_args)
        assert expires_date in str(call_args)

        # Step 4: View the access keys listing to confirm the key appears
        list_response = test_client.get(
            f"/object-store/{store_name}/access-keys", headers=auth_headers
        )
        assert list_response.status_code == HTTP_OK

        list_content = BeautifulSoup(list_response.text, features="html.parser")
        # Find our test key in the table
        assert (
            list_content.find(
                string=lambda s: "test-integration-key" in s if s else False
            )
            is not None
        )

        # Step 5: Delete the key
        delete_response = test_client.post(
            f"/object-store/{store_name}/access-keys",
            headers=auth_headers,
            data={"delete_access_key": "test-integration-key"},
            follow_redirects=False,
        )
        # Should redirect back to the access keys page
        assert delete_response.status_code == HTTP_POST_REDIRECT
        assert (
            f"/object-store/{store_name}/access-keys"
            in delete_response.headers["location"]
        )

        # Verify delete method was called with the right key
        mock_store.delete_key.assert_called_once_with("test-integration-key")


def test_key_creation_error_handling(test_client, auth_headers, config, store_name):
    """Test error handling during key creation.

    Verifies that when an error occurs during key creation:
    - The application displays an appropriate error message
    - The user is not redirected away from the page
    """
    # First authenticate with the store
    authenticate_with_store(test_client, auth_headers, store_name, config)

    # Use the correct URL format
    create_url = f"/object-store/{store_name}/create-keys"

    # Patch storefromjson to simulate an error condition
    with patch(
        "objectstore_interface.pages.access_key_pages.create.storefromjson"
    ) as mock_storefromjson:
        # Create a mock store that will simulate an error
        mock_store = MagicMock()
        mock_store.create_key.side_effect = Exception("Simulated key creation error")
        mock_storefromjson.return_value = mock_store

        # Submit form with data that should trigger an error
        expires_date = "invalid-date"
        error_response = test_client.post(
            create_url,
            headers=auth_headers,
            data={"description": TEST_KEY_DESCRIPTION, "expires": expires_date},
        )

        # Should get an error page
        assert error_response.status_code == HTTP_OK
        content = BeautifulSoup(error_response.text, features="html.parser")
        assert (
            content.find(string=lambda s: "Something went wrong" in s if s else False)
            is not None
        )


def test_key_deletion_error_handling(
    test_client, auth_headers, config, store_name, mock_key_data
):
    """Test error handling during key deletion.

    Verifies that when an error occurs during key deletion:
    - The application displays an appropriate error message
    - The user is not redirected away from the page
    """
    # First authenticate with the store
    authenticate_with_store(test_client, auth_headers, store_name, config)

    # Patch storefromjson to simulate a deletion error
    with patch(
        "objectstore_interface.object_store_classes.fromjson.storefromjson"
    ) as mock_storefromjson:
        # Create a mock store that will simulate an error during deletion
        mock_store = MagicMock()
        mock_store.get_store.return_value = {
            "status_code": 200,
            "access_keys": mock_key_data,
        }
        mock_store.delete_key.side_effect = Exception("Simulated deletion error")
        mock_storefromjson.return_value = mock_store

        # Attempt to delete a key, which should trigger an error
        error_response = test_client.post(
            f"/object-store/{store_name}/access-keys",
            headers=auth_headers,
            data={"delete_access_key": "test-integration-key"},
        )

        # Should get an error page
        assert error_response.status_code == HTTP_OK
        content = BeautifulSoup(error_response.text, features="html.parser")
        assert (
            content.find(string=lambda s: "Something went wrong" in s if s else False)
            is not None
        )


def test_expired_key_interaction(test_client, auth_headers, config, store_name):
    """Test interactions with expired keys.

    Verifies that expired keys:
    - Are displayed with appropriate styling
    - Have disabled delete buttons
    - Show an EXPIRED indicator
    """
    # First authenticate with the store
    authenticate_with_store(test_client, auth_headers, store_name, config)

    # Create expired key data
    today = datetime.now()
    expired_key_data = [
        {
            "name": "expired-test-key",
            "last_modified": today.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lifepoint": (today - relativedelta(days=1)).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            ),
            "lifepoint_date": today - relativedelta(days=1),
            "x_custom_meta_source": "Expired Test Key",
            "expiring": False,
            "expired": True,
        }
    ]

    # Define a flexible get_store method for our mock
    async def flexible_get_store(*args, **kwargs):
        """Handle any argument pattern for get_store"""
        return {
            "status_code": 200,
            "access_keys": expired_key_data,
        }

    # Set up patching for view.storefromjson
    with patch(
        "objectstore_interface.pages.access_key_pages.view.storefromjson"
    ) as mock_storefromjson:
        # Create a mock store that will return expired keys
        mock_store = MagicMock()
        mock_store.get_store = AsyncMock(side_effect=flexible_get_store)

        # Configure the toJSON method
        mock_store.toJSON.return_value = json.dumps(
            {
                "type": "DataCore",
                "location": f"{store_name}.s3.jc.rl.ac.uk",
                "auth_access_key": "test-key",
            }
        )
        mock_storefromjson.return_value = mock_store

        # Set up session mock
        with patch(
            "objectstore_interface.pages.access_key_pages.view.Request.session",
            new_callable=PropertyMock,
        ) as mock_session:
            # Create session dict with the right keys
            session_dict = {
                store_name: mock_store.toJSON(),
                f"access_key_{store_name}": "test-key",
            }
            mock_session.return_value = session_dict

            # View the keys listing
            list_response = test_client.get(
                f"/object-store/{store_name}/access-keys", headers=auth_headers
            )
            assert list_response.status_code == HTTP_OK

        # Verify key display and behavior
        list_content = BeautifulSoup(list_response.text, features="html.parser")

        # Should show the expired key with appropriate styling
        assert (
            list_content.find(string=lambda s: "expired-test-key" in s if s else False)
            is not None
        )

        # Should have EXPIRED indicator
        assert (
            list_content.find(string=lambda s: "EXPIRED" in s if s else False)
            is not None
        )

        # Verify the delete button is disabled for expired keys
        delete_button = list_content.find(
            "button", {"name": "delete_access_key_btn", "disabled": True}
        )
        assert delete_button is not None
