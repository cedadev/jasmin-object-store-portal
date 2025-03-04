import json
import pytest
from unittest.mock import patch, MagicMock, mock_open
from objectstore_interface.object_store_classes.datacore import DataCore


class TestBucketOperations:
    @pytest.fixture
    def datacore(self):
        """Fixture for creating a basic DataCore instance."""
        dc = DataCore(location="test-bucket.s3.example.com")
        dc.s3_auth_access_key = "test-s3-key"
        return dc

    @pytest.fixture
    def mock_bucket_data(self):
        """Fixture for common bucket data."""
        return {
            "Buckets": [
                {"Name": "bucket1", "CreationDate": "2023-01-01T00:00:00Z"},
                {"Name": "bucket2", "CreationDate": "2023-02-01T00:00:00Z"},
            ]
        }

    @pytest.fixture
    def mock_policy_data(self):
        """Fixture for common policy data."""
        return {"Version": "2008-10-17", "Statement": [{"Effect": "Allow"}]}

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.boto3.Session")
    @patch(
        "objectstore_interface.object_store_classes.datacore.open",
        new_callable=mock_open,
    )
    @patch("objectstore_interface.object_store_classes.datacore.yaml.safe_load")
    async def test_list_buckets(
        self, mock_yaml_load, mock_file, mock_session, datacore, mock_bucket_data
    ):
        """Test listing buckets."""
        # Setup mocks
        mock_yaml_load.return_value = {"s3": {"auth_secret": "test-secret"}}

        mock_client = MagicMock()
        mock_client.list_buckets.return_value = mock_bucket_data

        mock_session_instance = MagicMock()
        mock_session_instance.client.return_value = mock_client
        mock_session.return_value = mock_session_instance

        # Call the method
        result = await datacore.get_buckets()

        # Assertions
        assert len(result) == 2
        assert result[0]["Name"] == "bucket1"
        assert result[1]["Name"] == "bucket2"

        # Verify the session was created correctly
        mock_session_instance.client.assert_called_once_with(
            "s3",
            endpoint_url=f"http://{datacore.location}",
            aws_access_key_id="test-s3-key",
            aws_secret_access_key="test-secret",
        )

    @pytest.mark.asyncio
    @patch(
        "objectstore_interface.object_store_classes.datacore.DataCore._init_bucket_resource"
    )
    async def test_get_bucket_details(
        self, mock_init_resource, datacore, mock_policy_data
    ):
        """Test getting details of a bucket."""
        # Setup mocks
        mock_policy = MagicMock()
        mock_policy.policy = json.dumps(mock_policy_data)

        mock_bucket = MagicMock()
        mock_bucket.Policy.return_value = mock_policy

        mock_init_resource.return_value = mock_bucket

        # Call the method
        result = await datacore.get_bucket_details("test-bucket")

        # Assertions
        assert result["hasPolicy"] is True
        assert len(result["policy"]) == 1
        assert result["policy"][0]["Effect"] == "Allow"

        # Verify the resource was initialized correctly
        mock_init_resource.assert_called_once_with("test-bucket")

    @pytest.mark.asyncio
    @patch(
        "objectstore_interface.object_store_classes.datacore.DataCore._init_bucket_resource"
    )
    async def test_get_bucket_details_no_policy(self, mock_init_resource, datacore):
        """Test getting details of a bucket without a policy."""
        # Setup mocks
        mock_bucket = MagicMock()
        mock_bucket.Policy.side_effect = Exception("No policy exists")
        mock_init_resource.return_value = mock_bucket

        # Call the method
        result = await datacore.get_bucket_details("test-bucket")

        # Assertions
        assert result["hasPolicy"] is False
        assert result["policy"] == []
