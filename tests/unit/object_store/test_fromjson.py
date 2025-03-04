import pytest
import json
from objectstore_interface.object_store_classes.fromjson import storefromjson
from objectstore_interface.object_store_classes.datacore import DataCore
from objectstore_interface.object_store_classes.base import ObjectStore


class TestFromJson:
    @pytest.fixture
    def datacore_instance(self):
        """Fixture providing a configured DataCore instance for testing."""
        dc = DataCore(location="test-bucket.s3.example.com")
        dc.auth_access_key = "test-key"
        dc.s3_auth_access_key = "test-s3-key"
        return dc

    def test_datacore_serialization_deserialization(self, datacore_instance):
        """Test that a DataCore object can be serialized and deserialized correctly."""
        # Serialize the object to JSON
        json_str = datacore_instance.toJSON()

        # Verify JSON string contains expected data
        json_data = json.loads(json_str)
        print(json_data)
        assert json_data["location"] == "test-bucket.s3.example.com"
        assert json_data["auth_access_key"] == "test-key"

        # Deserialize back to an object
        deserialized = storefromjson(json_str)

        # Verify all properties were maintained
        assert deserialized.name == datacore_instance.name
        assert deserialized.location == datacore_instance.location
        assert deserialized.type == datacore_instance.type
        assert deserialized.auth_access_key == datacore_instance.auth_access_key
        assert deserialized.s3_auth_access_key == datacore_instance.s3_auth_access_key

    def test_base_object_store_serialization(self):
        """Test serialization and deserialization of the base ObjectStore class."""
        # Create and configure a base ObjectStore
        original = ObjectStore(name="test-store", location="test-location")

        # Serialize
        json_str = original.toJSON()

        # Deserialize
        deserialized = storefromjson(json_str)

        # Verify properties
        assert deserialized.name == "test-store"
        assert deserialized.location == "test-location"
        assert deserialized.type == "ObjectStore"

    def test_malformed_json_handling(self):
        """Test handling of malformed JSON input."""
        malformed_json = "{invalid: json}"

        # The function should raise an exception for malformed JSON
        with pytest.raises(Exception):
            storefromjson(malformed_json)

    def test_missing_type_field(self):
        """Test handling JSON without a required 'type' field."""
        # Create JSON without the type field
        invalid_json = json.dumps({"name": "test", "location": "test-loc"})

        # The function should handle missing type information
        with pytest.raises(KeyError):
            storefromjson(invalid_json)

    def test_unknown_type_handling(self):
        """Test handling of JSON with unknown object type."""
        # Create JSON with unknown type
        unknown_type_json = json.dumps(
            {"type": "UnknownStore", "name": "test", "location": "test-loc"}
        )

        # Function should return a base ObjectStore when type is unknown
        result = storefromjson(unknown_type_json)
        assert isinstance(result, ObjectStore)
        assert result.name == "test"
        assert result.location == "test-loc"
