import pytest
import json
from unittest.mock import patch, MagicMock, mock_open
from objectstore_interface.object_store_classes.datacore import DataCore


class TestPolicyManagement:
    @pytest.fixture
    def datacore(self):
        """Fixture for creating a basic DataCore instance."""
        return DataCore(location="test-bucket.s3.example.com")

    @pytest.fixture
    def mock_yaml_config(self):
        """Fixture for mocking the YAML configuration."""
        return {"s3": {"auth_secret": "test-secret"}}

    @pytest.fixture
    def mock_s3_client(self):
        """Fixture for mocking the S3 client."""
        client = MagicMock()
        return client

    @pytest.mark.asyncio
    @patch(
        "objectstore_interface.object_store_classes.datacore.DataCore._init_bucket_resource"
    )
    @patch("objectstore_interface.object_store_classes.datacore.boto3.client")
    @patch(
        "objectstore_interface.object_store_classes.datacore.open",
        new_callable=mock_open,
    )
    @patch("objectstore_interface.object_store_classes.datacore.yaml.safe_load")
    async def test_delete_policy(
        self, mock_yaml_load, mock_file, mock_boto_client, mock_init_resource, datacore
    ):
        """
        Test policy deletion.

        Verifies that:
        1. A policy can be deleted by index
        2. The correct policy is removed from the bucket policy
        3. The updated policy is properly sent back to the service
        """
        # Setup mocks
        mock_yaml_load.return_value = {"s3": {"auth_secret": "test-secret"}}

        # Create sample policy with two statements
        original_policy = {
            "Version": "2008-10-17",
            "Statement": [
                {
                    "Sid": "Policy0",
                    "Effect": "Allow",
                    "Principal": {"AWS": ["arn:aws:iam::123456789012:user/user1"]},
                    "Action": ["s3:GetObject"],
                    "Resource": ["arn:aws:s3:::test-bucket/*"],
                },
                {
                    "Sid": "Policy1",
                    "Effect": "Deny",
                    "Principal": {"AWS": ["arn:aws:iam::123456789012:user/user2"]},
                    "Action": ["s3:DeleteObject"],
                    "Resource": ["arn:aws:s3:::test-bucket/*"],
                },
            ],
        }

        # Setup bucket policy mock
        mock_policy = MagicMock()
        mock_policy.policy = json.dumps(original_policy)
        mock_bucket = MagicMock()
        mock_bucket.Policy.return_value = mock_policy
        mock_init_resource.return_value = mock_bucket

        # Setup S3 client mock
        mock_s3_client = MagicMock()
        mock_boto_client.return_value = mock_s3_client

        # Set auth key
        datacore.s3_auth_access_key = "test-s3-key"

        # Call the method to delete first policy (index 0)
        result = await datacore.delete_policy("test-bucket", "0")

        # Assert response status code
        assert result["status_code"] == 200

        # Verify resource initialization
        mock_init_resource.assert_called_once_with("test-bucket")

        # Verify S3 client creation
        mock_boto_client.assert_called_once_with(
            "s3",
            endpoint_url="http://test-bucket.s3.example.com",
            aws_access_key_id="test-s3-key",
            aws_secret_access_key="test-secret",
        )

        # Verify policy update
        mock_s3_client.put_bucket_policy.assert_called_once()
        call_args = mock_s3_client.put_bucket_policy.call_args
        assert call_args[1]["Bucket"] == "test-bucket"

        # Verify updated policy content
        policy_str = call_args[1]["Policy"]
        updated_policy = json.loads(policy_str)
        assert len(updated_policy["Statement"]) == 1
        assert updated_policy["Statement"][0]["Sid"] == "Policy1"

    @pytest.mark.asyncio
    @patch(
        "objectstore_interface.object_store_classes.datacore.DataCore._init_bucket_resource"
    )
    @patch("objectstore_interface.object_store_classes.datacore.boto3.client")
    @patch(
        "objectstore_interface.object_store_classes.datacore.open",
        new_callable=mock_open,
    )
    @patch("objectstore_interface.object_store_classes.datacore.yaml.safe_load")
    async def test_delete_policy_empty_policy(
        self, mock_yaml_load, mock_file, mock_boto_client, mock_init_resource, datacore
    ):
        """
        Test deletion when there's only one policy left.

        Verifies that:
        1. Deleting the last policy results in an empty policy statement list
        2. The updated empty policy is properly sent back to the service
        """
        # Setup mocks
        mock_yaml_load.return_value = {"s3": {"auth_secret": "test-secret"}}

        # Create sample policy with one statement
        original_policy = {
            "Version": "2008-10-17",
            "Statement": [
                {
                    "Sid": "LastPolicy",
                    "Effect": "Allow",
                    "Principal": {"AWS": ["arn:aws:iam::123456789012:user/user1"]},
                    "Action": ["s3:GetObject"],
                    "Resource": ["arn:aws:s3:::test-bucket/*"],
                }
            ],
        }

        # Setup bucket policy mock
        mock_policy = MagicMock()
        mock_policy.policy = json.dumps(original_policy)
        mock_bucket = MagicMock()
        mock_bucket.Policy.return_value = mock_policy
        mock_init_resource.return_value = mock_bucket

        # Setup S3 client mock
        mock_s3_client = MagicMock()
        mock_boto_client.return_value = mock_s3_client
        datacore.s3_auth_access_key = "test-s3-key"

        # Call the method to delete the only policy (index 0)
        result = await datacore.delete_policy("test-bucket", "0")

        # Verify result
        assert result["status_code"] == 200

        # Verify policy update - should have empty statement list
        call_args = mock_s3_client.put_bucket_policy.call_args
        updated_policy = json.loads(call_args[1]["Policy"])
        assert len(updated_policy["Statement"]) == 0

    @pytest.mark.asyncio
    @patch(
        "objectstore_interface.object_store_classes.datacore.DataCore._init_bucket_resource"
    )
    async def test_get_individual_policy(self, mock_init_resource, datacore):
        """
        Test retrieving an individual policy by index.

        Verifies that:
        1. A policy can be retrieved by its index
        2. The correct policy data is returned
        3. Invalid index returns an empty dict
        """
        # Create sample policy with multiple statements
        sample_policy = {
            "Version": "2008-10-17",
            "Statement": [
                {
                    "Sid": "Policy0",
                    "Effect": "Allow",
                    "Principal": {"user": ["user1"]},
                    "Action": ["s3:GetObject"],
                    "Resource": "*",
                },
                {
                    "Sid": "Policy1",
                    "Effect": "Deny",
                    "Principal": {"group": ["admin"]},
                    "Action": ["s3:DeleteObject"],
                    "Resource": "*",
                },
            ],
        }

        # Setup mock bucket and policy
        mock_policy = MagicMock()
        mock_policy.policy = json.dumps(sample_policy)
        mock_bucket = MagicMock()
        mock_bucket.Policy.return_value = mock_policy
        mock_init_resource.return_value = mock_bucket

        # Test retrieving valid policy at index 1
        result = await datacore.get_individual_policy("test-bucket", "1")

        # Verify correct policy data returned
        assert result["Sid"] == "Policy1"
        assert result["Effect"] == "Deny"
        assert result["Principal"]["group"] == ["admin"]

        # Test retrieving policy with invalid index
        empty_result = await datacore.get_individual_policy("test-bucket", "5")
        assert empty_result == {}
