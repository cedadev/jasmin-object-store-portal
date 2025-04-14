from unittest.mock import MagicMock
import pytest

from objectstore_interface.object_store_classes.base import ObjectStore


class TestObjectStoreBase:
    @pytest.fixture
    def object_store(self):
        """Fixture providing a basic ObjectStore instance for tests."""
        return ObjectStore(name="test-store", location="test-location")

    def test_object_store_init(self, object_store):
        """Test that the base ObjectStore constructor sets attributes correctly."""
        assert object_store.name == "test-store"
        assert object_store.location == "test-location"

    def test_return_error(self, object_store):
        """Test the _return_error helper method."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        # Execute method under test
        error = object_store._return_error(mock_response)

        # Assert expected results
        assert error["status_code"] == 404
        assert error["error"] == "404: Not Found"

    def test_return_error_with_different_code(self, object_store):
        """Test the _return_error helper with a different status code."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        error = object_store._return_error(mock_response)

        assert error["status_code"] == 500
        assert error["error"] == "500: Internal Server Error"
