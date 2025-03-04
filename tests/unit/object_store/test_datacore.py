import json
import pytest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import Request

from objectstore_interface.object_store_classes.datacore import DataCore


@pytest.fixture
def datacore():
    """Fixture for creating a basic DataCore instance."""
    dc = DataCore(location="test-bucket.s3.example.com")
    # Pre-set common attributes to reduce duplication
    dc.auth_access_key = "test-auth-key"
    dc.s3_auth_access_key = "test-s3-key"
    return dc


@pytest.fixture
def mock_request():
    """Fixture for creating a mock request with session data."""
    mock_req = MagicMock(spec=Request)
    mock_req.session = {"token": {"userinfo": {"preferred_username": "testuser"}}}
    return mock_req


@pytest.fixture
def mock_config():
    """Fixture for mocking configuration file."""
    return {"s3": {"auth_secret": "test-secret"}, "testing": True}


@pytest.fixture
def mock_yaml_config():
    """Fixture for mocking YAML config loader."""
    with patch(
        "objectstore_interface.object_store_classes.datacore.yaml.safe_load"
    ) as mock_yaml:
        mock_yaml.return_value = {"s3": {"auth_secret": "test-secret"}}
        yield mock_yaml


@pytest.fixture
def mock_file_open():
    """Fixture for mocking file operations."""
    with patch(
        "objectstore_interface.object_store_classes.datacore.open",
        new_callable=mock_open,
    ) as m:
        yield m


@pytest.fixture
def future_date():
    """Generate a future date string in HTTP format."""
    future = datetime.today() + relativedelta(weeks=2)
    return future.strftime("%a, %d %b %Y %H:%M:%S GMT")


@pytest.fixture
def mock_bucket():
    """Fixture for creating a mock S3 bucket resource."""
    mock_bucket = MagicMock()
    return mock_bucket


class TestDataCoreInit:
    def test_init_sets_correct_attributes(self):
        """Test that constructor sets attributes correctly."""
        datacore = DataCore(location="test-bucket.s3.example.com", name="custom-name")

        assert datacore.location == "test-bucket.s3.example.com"
        assert datacore.name == "test-bucket"  # Name extraction from location
        assert datacore.type == "Datacore"

    def test_init_with_minimal_params(self):
        """Test initialization with just location."""
        datacore = DataCore(location="minimal.s3.example.com")

        assert datacore.location == "minimal.s3.example.com"
        assert datacore.name == "minimal"  # Name extracted from location
        assert datacore.type == "Datacore"


class TestDataCoreGetStore:
    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    async def test_get_store_success(self, mock_r, datacore, future_date):
        """Test successful retrieval of store details."""
        # Setup mocks
        lifepoint_str = f"[{future_date}] reps=2, [] delete"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "test-key",
                "last_modified": "2023-06-01T10:30:00Z",
                "lifepoint": lifepoint_str,
                "x_custom_meta_source": "Test key",
                "x_owner_meta": "testuser",
            }
        ]
        mock_r.get.return_value = mock_response

        # Call the method
        result = await datacore.get_store(MagicMock())

        # Assertions
        assert result["status_code"] == 200
        assert len(result["access_keys"]) == 1
        assert result["access_keys"][0]["name"] == "test-key"
        assert result["access_keys"][0]["description"] == "Test key"
        assert not result["access_keys"][0]["expired"]

        # Verify the request was made correctly
        mock_r.get.assert_called_once_with(
            f"http://{datacore.location}:81/.TOKEN/?format=json",
            headers={"Cookie": f"token={datacore.auth_access_key}"},
        )

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    async def test_get_store_with_expired_keys(self, mock_r, datacore):
        """Test store retrieval with expired keys."""
        # Configure mocks
        past_date = datetime.today() - timedelta(days=7)
        lifepoint_str = (
            f"[{past_date.strftime('%a, %d %b %Y %H:%M:%S GMT')}] reps=2, [] delete"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "expired-key",
                "last_modified": "2023-01-01T10:30:00Z",
                "lifepoint": lifepoint_str,
                "x_custom_meta_source": "Expired key",
                "x_owner_meta": "testuser",
            }
        ]
        mock_r.get.return_value = mock_response

        # Call the method
        result = await datacore.get_store(MagicMock())

        # Assertions
        assert result["status_code"] == 200
        assert len(result["access_keys"]) == 1
        assert result["access_keys"][0]["name"] == "expired-key"
        assert result["access_keys"][0]["expired"]

        # Verify correct endpoint was called
        mock_r.get.assert_called_once()

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    async def test_get_store_error_response(self, mock_r, datacore):
        """Test handling of error response."""
        # Setup mock error response
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Access denied"
        mock_r.get.return_value = mock_response

        # Call the method
        result = await datacore.get_store(MagicMock())

        # Assertions
        assert result["status_code"] == 403
        assert result["error"] == "403: Access denied"
        assert "access_keys" not in result


class TestDataCoreDeleteKey:
    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    async def test_delete_key_success(self, mock_r, datacore):
        """Test successful key deletion."""
        # Setup successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_r.delete.return_value = mock_response

        # Call the method
        result = await datacore.delete_key("key-to-delete")

        # Assertions
        assert result["status_code"] == 200
        assert result["error"] is None

        # Verify the request was made correctly
        mock_r.delete.assert_called_once_with(
            f"http://{datacore.location}:81/.TOKEN/key-to-delete",
            headers={"Cookie": f"token={datacore.auth_access_key}"},
        )

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    async def test_delete_key_error(self, mock_r, datacore):
        """Test error handling during key deletion."""
        # Setup error response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Key not found"
        mock_r.delete.return_value = mock_response

        # Call the method
        result = await datacore.delete_key("nonexistent-key")

        # Assertions
        assert result["status_code"] == 404
        assert result["error"] == "404: Key not found"


class TestDataCoreCreateKey:
    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    @patch("objectstore_interface.object_store_classes.datacore.random.choices")
    async def test_create_key_success(self, mock_choices, mock_r, datacore):
        """Test successful key creation."""
        # Setup mocks
        mock_choices.return_value = list("abcde12345")

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = (
            "Token new-access-key issued for test in test-bucket.s3.example.com"
        )
        mock_r.post.return_value = mock_response

        # Call the method with just the two required parameters
        result = await datacore.create_key("Test key", "2023-12-31")
        # Assertions
        assert result["status_code"] == 201
        assert result["access_key"] == "new-access-key"
        assert result["secret_key"] == "abcde12345"

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    async def test_create_key_error(self, mock_r, datacore):
        """Test error handling during key creation."""
        # Setup error response
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Permission denied"
        mock_r.post.return_value = mock_response

        # Call the method
        result = await datacore.create_key("Test key", "2023-12-31")

        # Assertions
        assert result["status_code"] == 403
        assert result["error"] == "403: Permission denied"
        assert "access_key" not in result
        assert "secret_key" not in result


class TestDataCoreGetAccessKey:
    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    async def test_get_existing_access_key(
        self,
        mock_r,
        mock_request,
        mock_yaml_config,
        mock_file_open,
        datacore,
        future_date,
    ):
        """Test retrieving an existing access key."""
        # Setup mock response with existing keys
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "auth-key",
                "lifepoint": f"[{future_date}] reps=2, [] delete",
                "x_custom_meta_source": "JASMIN account auth access key",
            },
            {
                "name": "s3-auth-key",
                "lifepoint": f"[{future_date}] reps=2, [] delete",
                "x_custom_meta_source": "JASMIN account auth access key S3",
            },
        ]
        mock_r.get.return_value = mock_response

        # Call the method
        result = await datacore.get_access_key("password123", mock_request)

        # Assertions
        assert result["status_code"] == 200
        assert result["access_key"] == "auth-key"
        assert result["s3_access_key"] == "s3-auth-key"
        assert datacore.auth_access_key == "auth-key"
        assert datacore.s3_auth_access_key == "s3-auth-key"

        # Verify the request was made correctly
        mock_r.get.assert_called_once()

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.r")
    async def test_create_new_access_keys(
        self, mock_r, mock_request, mock_yaml_config, mock_file_open, datacore
    ):
        """Test creating new access keys when none exist."""
        # Setup mock responses
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = []  # No existing keys

        # Mock first POST response (auth key)
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.text = "Token auth-key issued for test"

        # Mock second POST response (S3 auth key)
        mock_s3_response = MagicMock()
        mock_s3_response.status_code = 200
        mock_s3_response.text = "Token s3-auth-key issued for test"

        mock_r.get.return_value = mock_get_response
        mock_r.post.side_effect = [mock_auth_response, mock_s3_response]

        # Call the method
        result = await datacore.get_access_key("password123", mock_request)

        # Assertions
        assert result["status_code"] == 200
        assert result["access_key"] == "auth-key"
        assert result["s3_access_key"] == "s3-auth-key"
        assert datacore.auth_access_key == "auth-key"
        assert datacore.s3_auth_access_key == "s3-auth-key"

        # Verify the POST requests were made correctly
        assert mock_r.post.call_count == 2


class TestDataCoreBucketOperations:
    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.boto3.Session")
    async def test_get_buckets(
        self, mock_session, datacore, mock_yaml_config, mock_file_open
    ):
        """Test retrieving buckets list."""
        # Setup mock boto3 client
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [
                {"Name": "bucket1", "CreationDate": datetime.now()},
                {"Name": "bucket2", "CreationDate": datetime.now()},
            ]
        }

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
    async def test_get_bucket_details_with_policy(self, datacore, mock_bucket):
        """Test getting bucket details with an existing policy."""
        # Setup policy mock
        policy_json = '{"Version":"2008-10-17","Statement":[{"Effect":"Allow"}]}'
        mock_policy = MagicMock()
        mock_policy.policy = policy_json
        mock_bucket.Policy.return_value = mock_policy

        # Patch the _init_bucket_resource method
        with patch.object(datacore, "_init_bucket_resource", return_value=mock_bucket):
            # Call the method
            result = await datacore.get_bucket_details("test-bucket")

            # Assertions
            assert result["hasPolicy"] is True
            assert len(result["policy"]) == 1
            assert result["policy"][0]["Effect"] == "Allow"

            # Verify resource was initialized with correct bucket name
            datacore._init_bucket_resource.assert_called_once_with("test-bucket")

    @pytest.mark.asyncio
    async def test_get_bucket_details_no_policy(self, datacore, mock_bucket):
        """Test getting bucket details when no policy exists."""
        # Setup bucket to raise exception when Policy is accessed
        mock_bucket.Policy.side_effect = Exception("No policy")

        # Patch the _init_bucket_resource method
        with patch.object(datacore, "_init_bucket_resource", return_value=mock_bucket):
            # Call the method
            result = await datacore.get_bucket_details("test-bucket")

            # Assertions
            assert result["hasPolicy"] is False
            assert result["policy"] == []

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.boto3.client")
    async def test_create_policy(
        self, mock_client, datacore, mock_bucket, mock_yaml_config, mock_file_open
    ):
        """Test policy creation."""
        # Setup policy mock
        policy_json = '{"Version":"2008-10-17","Statement":[]}'
        mock_policy = MagicMock()
        mock_policy.policy = policy_json
        mock_bucket.Policy.return_value = mock_policy

        # Setup boto3 client mock
        mock_s3_client = MagicMock()
        mock_client.return_value = mock_s3_client

        # Patch the _init_bucket_resource method
        with patch.object(datacore, "_init_bucket_resource", return_value=mock_bucket):
            # Call the method with multiple users and groups
            result = await datacore.create_policy(
                actions="GetObject,PutObject",
                groups="group1,group2",
                users="user1,user2",
                application="Users",
                name="TestPolicy",
                direction="Allow",
                bucket="test-bucket",
            )

            # Assertions
            assert result["status_code"] == 200

            # Verify put_bucket_policy was called with updated policy
            mock_s3_client.put_bucket_policy.assert_called_once()
            call_args = mock_s3_client.put_bucket_policy.call_args
            assert call_args[1]["Bucket"] == "test-bucket"

            # Check policy contents
            policy_str = call_args[1]["Policy"]
            policy = json.loads(policy_str)
            assert len(policy["Statement"]) == 1
            assert policy["Statement"][0]["Sid"] == "TestPolicy"
            assert policy["Statement"][0]["Effect"] == "Allow"
            assert "GetObject" in policy["Statement"][0]["Action"]
            assert "PutObject" in policy["Statement"][0]["Action"]

    @pytest.mark.asyncio
    @patch("objectstore_interface.object_store_classes.datacore.boto3")
    async def test_init_bucket_resource(
        self, mock_boto3, mock_yaml_config, mock_file_open
    ):
        """Test the initialization of a bucket resource."""
        # Setup boto3 mocks
        mock_session = MagicMock()
        mock_s3_resource = MagicMock()
        mock_bucket = MagicMock()

        # Configure boto3 mocks
        mock_boto3.Session.return_value = mock_session
        mock_session.resource.return_value = mock_s3_resource
        mock_s3_resource.Bucket.return_value = mock_bucket

        # Create a DataCore instance with auth key
        datacore = DataCore("test-endpoint.s3.jc.rl.ac.uk")
        datacore.s3_auth_access_key = "test-access-key"

        # Execute the method
        result = await datacore._init_bucket_resource("test-bucket")

        # Assertions
        assert result == mock_bucket

        # Verify Session was created with correct parameters
        mock_session.resource.assert_called_once_with(
            "s3",
            endpoint_url="http://test-endpoint.s3.jc.rl.ac.uk",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret",
        )

        # Verify bucket was retrieved with correct name
        mock_s3_resource.Bucket.assert_called_once_with("test-bucket")


class TestDataCoreIndividualPolicy:
    @pytest.mark.asyncio
    async def test_get_individual_policy(self, datacore, mock_bucket):
        """Test retrieving an individual policy."""
        # Setup multi-policy mock
        policy_json = (
            '{"Version":"2008-10-17","Statement":[{"Sid":"Policy1"},{"Sid":"Policy2"}]}'
        )
        mock_policy = MagicMock()
        mock_policy.policy = policy_json
        mock_bucket.Policy.return_value = mock_policy

        # Patch the _init_bucket_resource method
        with patch.object(datacore, "_init_bucket_resource", return_value=mock_bucket):
            # Call the method to get the second policy (index 1)
            result = await datacore.get_individual_policy("test-bucket", "1")

            # Assertions
            assert result["Sid"] == "Policy2"

            # Verify resource was initialized with correct bucket name
            datacore._init_bucket_resource.assert_called_once_with("test-bucket")

    @pytest.mark.asyncio
    async def test_get_invalid_policy_index(self, datacore, mock_bucket):
        """Test retrieving a policy with invalid index."""
        # Setup policy mock
        policy_json = '{"Version":"2008-10-17","Statement":[{"Sid":"SinglePolicy"}]}'
        mock_policy = MagicMock()
        mock_policy.policy = policy_json
        mock_bucket.Policy.return_value = mock_policy

        # Patch the _init_bucket_resource method
        with patch.object(datacore, "_init_bucket_resource", return_value=mock_bucket):
            # Call the method with out-of-bounds index
            result = await datacore.get_individual_policy("test-bucket", "5")

            # Assert result is empty because index is out of bounds
            assert result == {}
