# tests/integration/conftest.py
from unittest.mock import MagicMock, patch
import pytest
import json
import yaml
from fastapi.testclient import TestClient

from objectstore_interface.main import app
from objectstore_interface.object_store_classes.datacore import DataCore


@pytest.fixture
def test_client():
    """Provides a FastAPI TestClient for integration tests."""
    client = TestClient(app)
    return client


@pytest.fixture
def auth_headers():
    """Provides authentication headers using the same token structure as unit tests."""
    # Load the token from test.json with the proper structure including userinfo
    with open("tests/test.json") as token_json:
        token_str = json.load(token_json)

    # Use the same structure as in test_main_routes.py
    token = {"options": {"token": token_str}}

    return {"token": json.dumps(token)}


@pytest.fixture
def mock_object_store_session():
    """Mock session storage and access so tests don't fail at session key checks."""
    # First patch the session access
    with patch(
        "objectstore_interface.pages.access_key_pages.bucket.Request", autospec=True
    ) as mock_request:
        # Create a mock session that returns a value for any key
        mock_session = MagicMock()
        mock_session.__getitem__.side_effect = lambda key: json.dumps(
            {"type": "Datacore", "location": f"{key}.example.com"}
        )

        # Set up the request.session attribute chain
        mock_request.return_value.session = mock_session

        # Then patch the storefromjson function that processes the session value
        with patch(
            "objectstore_interface.pages.access_key_pages.bucket.storefromjson"
        ) as mock_storefromjson:
            # Create a mock DataCore object
            mock_store = MagicMock(spec=DataCore)

            # Configure mock to return test data
            mock_store.get_buckets.return_value = [
                {"Name": "test-bucket", "CreationDate": "2023-01-01T00:00:00Z"}
            ]

            # Make storefromjson return our mock regardless of input
            mock_storefromjson.return_value = mock_store

            yield mock_store
