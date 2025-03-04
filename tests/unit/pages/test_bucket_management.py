from unittest import mock
import pytest
from unittest.mock import patch, MagicMock, AsyncMock as UnitTestAsyncMock
from objectstore_interface.pages.access_key_pages.bucket import view_buckets
from objectstore_interface.pages.bucket_pages.create_bucket import (
    permissions_page,
    create_permissions,
    template_permissions,
)
from botocore.exceptions import ClientError

from objectstore_interface.pages.bucket_pages.policies import (
    delete_policy,
    view_permissions,
)


# Use our own AsyncMock instead of importing from test_main_routes
# This improves isolation between test modules
class AsyncMock(UnitTestAsyncMock):
    """AsyncMock wrapper for compatibility with older Python versions."""

    pass


# Constants for commonly used test values
TEST_STORE = "test-store"
TEST_STORE_JSON = "test-store-json"
TEST_BUCKET = "test-bucket"
TEST_REDIRECT_URL = f"/object-store/{TEST_STORE}/buckets/{TEST_BUCKET}/policy"
TEST_CREATE_URL = f"/object-store/{TEST_STORE}/buckets/{TEST_BUCKET}/create"


@pytest.fixture
def mock_request():
    """
    Mock request object with a session dictionary.

    Returns:
        MagicMock: A mock of a FastAPI request with session data
    """
    request = MagicMock()
    request.session = {TEST_STORE: TEST_STORE_JSON}
    return request


@pytest.fixture
def mock_templates():
    """
    Mock templates to avoid actual template rendering.

    Yields:
        MagicMock: A mock of the Jinja2Templates class
    """
    with patch(
        "objectstore_interface.pages.access_key_pages.bucket.templates"
    ) as mock_templates:
        mock_template_response = MagicMock()
        mock_templates.TemplateResponse.return_value = mock_template_response
        yield mock_templates


@pytest.fixture
def mock_store():
    """
    Create a mock ObjectStore instance with async methods.

    Returns:
        MagicMock: A configured mock of the ObjectStore class
    """
    mock_store = MagicMock()
    mock_store.get_buckets = AsyncMock()
    mock_store.create_policy = AsyncMock()
    # Add commonly used methods to avoid repetition in tests
    mock_store.get_bucket_details = AsyncMock()
    mock_store.get_individual_policy = AsyncMock()
    mock_store.delete_policy = AsyncMock()
    return mock_store


@pytest.fixture
def mock_redirect():
    """
    Mock RedirectResponse to simplify assertions.

    Returns:
        MagicMock: A mock of RedirectResponse with configured return value
    """
    with patch(
        "objectstore_interface.pages.bucket_pages.policies.RedirectResponse"
    ) as mock_red:
        mock_instance = MagicMock()
        mock_red.return_value = mock_instance
        yield mock_red


@pytest.fixture
def successful_policy_response():
    """
    Common successful policy response fixture.

    Returns:
        dict: A typical successful policy response
    """
    return {"status": "success"}


@pytest.mark.asyncio
@patch("objectstore_interface.pages.access_key_pages.bucket.storefromjson")
async def test_view_buckets_success(
    mock_storefromjson, mock_request, mock_templates, mock_store
):
    """Test successful bucket listing."""
    # Setup
    mock_storefromjson.return_value = mock_store
    mock_store.get_buckets.return_value = [
        {"Name": "test-bucket1", "CreationDate": "2023-01-01T00:00:00Z"},
        {"Name": "test-bucket2", "CreationDate": "2023-02-01T00:00:00Z"},
    ]

    # Execute
    result = await view_buckets(mock_request, TEST_STORE)

    # Assert
    mock_storefromjson.assert_called_once_with(TEST_STORE_JSON)
    mock_store.get_buckets.assert_called_once()
    mock_templates.TemplateResponse.assert_called_once()

    # Verify template context
    context = mock_templates.TemplateResponse.call_args[0][2]
    assert "buckets" in context
    assert len(context["buckets"]) == 2


@pytest.mark.asyncio
@patch("objectstore_interface.pages.access_key_pages.bucket.storefromjson")
@patch("objectstore_interface.pages.access_key_pages.bucket.RedirectResponse")
async def test_view_buckets_exception(
    mock_redirect, mock_storefromjson, mock_request, mock_templates, mock_store
):
    """Test bucket listing with an exception."""
    # Setup
    mock_storefromjson.return_value = mock_store
    mock_store.get_buckets.side_effect = Exception("Test exception")
    mock_redirect.return_value = MagicMock()

    # Execute
    result = await view_buckets(mock_request, TEST_STORE)

    # Assert
    assert mock_request.session["timeout"] == "true"
    mock_redirect.assert_called_once()


@pytest.mark.asyncio
@patch("objectstore_interface.pages.bucket_pages.create_bucket.templates")
async def test_permissions_page(mock_templates, mock_request):
    """Test the permissions page display."""
    # Execute
    result = await permissions_page(mock_request, TEST_STORE, TEST_BUCKET)

    # Assert
    mock_templates.TemplateResponse.assert_called_once()

    # Verify template context
    context = mock_templates.TemplateResponse.call_args[0][2]
    assert context["view"] == "create"
    assert context["storename"] == TEST_STORE
    assert context["bucket"] == TEST_BUCKET
    assert len(context["templates"]) == 6  # Check all templates are included


@pytest.mark.asyncio
@patch("objectstore_interface.pages.bucket_pages.create_bucket.storefromjson")
@patch("objectstore_interface.pages.bucket_pages.create_bucket.RedirectResponse")
async def test_create_permissions_success(
    mock_redirect,
    mock_storefromjson,
    mock_request,
    mock_store,
    successful_policy_response,
):
    """Test successful permission creation."""
    # Setup
    mock_storefromjson.return_value = mock_store
    mock_store.create_policy.return_value = successful_policy_response
    mock_redirect.return_value = MagicMock()

    # Test data
    action_array = "GetObject,ListBucket"
    application = "Users"
    policy_name = "Test Policy"
    direction = "Allow"
    edit = "false"
    user_names = "user1,user2"

    # Execute
    result = await create_permissions(
        mock_request,
        TEST_STORE,
        TEST_BUCKET,
        actionArray=action_array,
        application=application,
        policyName=policy_name,
        direction=direction,
        edit=edit,
        userNames=user_names,
        groupNames=None,
    )

    # Assert
    mock_storefromjson.assert_called_once_with(TEST_STORE_JSON)
    mock_store.create_policy.assert_called_once_with(
        action_array,
        None,
        user_names,
        application,
        policy_name,
        direction,
        TEST_BUCKET,
        edit,
    )
    mock_redirect.assert_called_once_with(TEST_REDIRECT_URL, status_code=303)


@pytest.mark.asyncio
@patch("objectstore_interface.pages.bucket_pages.create_bucket.storefromjson")
@patch("objectstore_interface.pages.bucket_pages.create_bucket.RedirectResponse")
async def test_create_permissions_client_error(
    mock_redirect, mock_storefromjson, mock_request, mock_store
):
    """Test permission creation with ClientError."""
    # Setup
    mock_storefromjson.return_value = mock_store
    mock_store.create_policy.side_effect = ClientError(
        {"Error": {"Code": "TestError"}}, "create_policy"
    )
    mock_redirect.return_value = MagicMock()

    # Execute
    result = await create_permissions(
        mock_request,
        TEST_STORE,
        TEST_BUCKET,
        actionArray="GetObject",
        application="Users",
        policyName="Test Policy",
        direction="Allow",
        edit="false",
        userNames=None,
        groupNames=None,
    )

    # Assert error handling
    assert mock_request.session["invalid"] is True
    mock_redirect.assert_called_once_with(TEST_CREATE_URL, status_code=303)


# Template-related tests can be parameterized to reduce duplication
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "template_name,expected_params",
    [
        (
            "read-only-all",
            {
                "actions": "GetObject",
                "groups": "null",
                "users": "null",
                "application": "Anonymous",
                "name": "Read-only access for Everyone",
                "direction": "Allow",
            },
        ),
        (
            "bucket-manage-users",
            {
                "actions": "CopyBucket,CreateBucket,DeleteBucket,GetBucket,ListBucket",
                "groups": "null",
                "users": "null",
                "application": "All",
                "name": "Grant bucket management to Users",
                "direction": "Allow",
            },
        ),
        (
            "full-access-users",
            {
                "actions": "*",
                "groups": "null",
                "users": "null",
                "direction": "Allow",
                "application": "All",
                "name": "Full access for Users",
            },
        ),
        (
            "no-uploads-no-login",
            {
                "actions": "*",
                "groups": "null",
                "users": "null",
                "application": "Anonymous",
                "name": "Prevent bucket uploads without login",
                "direction": "Deny",
            },
        ),
    ],
)
@patch("objectstore_interface.pages.bucket_pages.create_bucket.storefromjson")
@patch("objectstore_interface.pages.bucket_pages.create_bucket.RedirectResponse")
async def test_template_permissions(
    mock_redirect,
    mock_storefromjson,
    mock_request,
    mock_store,
    successful_policy_response,
    template_name,
    expected_params,
):
    """
    Test template permission creation using different templates.

    This parameterized test replaces multiple individual tests for each template.
    """
    # Setup
    mock_storefromjson.return_value = mock_store
    mock_store.create_policy.return_value = successful_policy_response
    mock_redirect.return_value = MagicMock()

    # Execute
    result = await template_permissions(
        mock_request, TEST_STORE, TEST_BUCKET, template=template_name
    )

    # Assert
    mock_storefromjson.assert_called_once_with(TEST_STORE_JSON)

    # Add the bucket parameter to expected params
    expected_call_params = {**expected_params, "bucket": TEST_BUCKET}
    mock_store.create_policy.assert_called_once_with(**expected_call_params)

    mock_redirect.assert_called_once_with(TEST_REDIRECT_URL, status_code=303)


@pytest.mark.asyncio
@patch("objectstore_interface.pages.bucket_pages.policies.storefromjson")
@patch("objectstore_interface.pages.bucket_pages.policies.templates")
async def test_view_permissions_success(
    mock_templates, mock_storefromjson, mock_request, mock_store
):
    """Test successful bucket policy viewing."""
    # Setup
    mock_storefromjson.return_value = mock_store
    # Configure the policy mock response
    test_policies = [
        {
            "Sid": "Test1",
            "Effect": "Allow",
            "Principal": {"user": ["user1"]},
            "Action": ["GetObject"],
        },
        {
            "Sid": "Test2",
            "Effect": "Deny",
            "Principal": {"anonymous": ["*"]},
            "Action": ["*"],
        },
    ]
    mock_store.get_bucket_details.return_value = {"Statement": test_policies}
    mock_templates.TemplateResponse.return_value = MagicMock()
    mock_request.session["invalid"] = False  # Set up session state for testing

    # Execute
    result = await view_permissions(mock_request, TEST_STORE, TEST_BUCKET)

    # Assert proper access to object store
    mock_storefromjson.assert_called_once_with(mock_request.session[TEST_STORE])
    mock_store.get_bucket_details.assert_called_once_with(TEST_BUCKET)

    # Verify template rendering with correct context
    mock_templates.TemplateResponse.assert_called_once()
    context = mock_templates.TemplateResponse.call_args[0][2]
    assert context["view"] == "view"
    assert context["policy"] == mock_store.get_bucket_details.return_value
    assert context["bucket"] == TEST_BUCKET
    assert not context["invalid"]


@pytest.mark.asyncio
@patch("objectstore_interface.pages.bucket_pages.policies.storefromjson")
@patch("objectstore_interface.pages.bucket_pages.policies.logging")
@patch("objectstore_interface.pages.bucket_pages.policies.traceback")
async def test_view_permissions_exception(
    mock_traceback,
    mock_logging,
    mock_storefromjson,
    mock_request,
    mock_store,
    mock_redirect,
):
    """Test bucket policy viewing with exception."""
    # Setup
    mock_storefromjson.return_value = mock_store
    # Configure exception in get_bucket_details
    test_exception = Exception("Test exception")
    mock_store.get_bucket_details.side_effect = test_exception
    # Configure traceback and redirect mocks
    mock_traceback.format_exception.return_value = ["Mocked traceback"]

    # Execute
    result = await view_permissions(mock_request, TEST_STORE, TEST_BUCKET)

    # Verify error handling
    mock_logging.error.assert_called_once()
    assert result == mock_redirect.return_value
    assert mock_request.session["timeout"] == "true"
    mock_redirect.assert_called_once()

    # Verify the redirect URL
    args, kwargs = mock_redirect.call_args
    assert args[0] == f"/object-store/{TEST_STORE}"


@pytest.mark.asyncio
@patch("objectstore_interface.pages.bucket_pages.policies.storefromjson")
async def test_delete_policy(
    mock_storefromjson,
    mock_request,
    mock_store,
    mock_redirect,
    successful_policy_response,
):
    """Test successful policy deletion."""
    # Setup
    mock_storefromjson.return_value = mock_store
    mock_store.delete_policy.return_value = successful_policy_response

    # Execute
    policy_index = "3"
    policy_param = f"delete_{policy_index}"
    result = await delete_policy(mock_request, TEST_STORE, TEST_BUCKET, policy_param)

    # Assert
    mock_storefromjson.assert_called_once_with(TEST_STORE_JSON)
    mock_store.delete_policy.assert_called_once_with(TEST_BUCKET, policy_index)
    mock_redirect.assert_called_once_with(TEST_REDIRECT_URL, status_code=303)


@pytest.mark.asyncio
@patch("objectstore_interface.pages.bucket_pages.policies.storefromjson")
@patch("objectstore_interface.pages.bucket_pages.policies.templates")
async def test_edit_policy(
    mock_templates, mock_storefromjson, mock_request, mock_store
):
    """Test edit policy flow."""
    # Setup
    mock_storefromjson.return_value = mock_store

    # Configure policy details for testing
    policy_details = {
        "Sid": "TestPolicy",
        "Effect": "Allow",
        "Principal": {"user": ["user1"]},
        "Action": ["GetObject"],
    }
    mock_store.get_bucket_details.return_value = {"Statement": [policy_details]}
    mock_store.get_individual_policy.return_value = policy_details
    mock_templates.TemplateResponse.return_value = MagicMock()

    # Execute - test with edit_0 parameter
    policy_index = "0"
    policy_param = f"edit_{policy_index}"
    result = await delete_policy(mock_request, TEST_STORE, TEST_BUCKET, policy_param)

    # Assert proper method calls
    mock_storefromjson.assert_called_once_with(TEST_STORE_JSON)
    mock_store.get_bucket_details.assert_called_once_with(TEST_BUCKET)
    mock_store.get_individual_policy.assert_called_once_with(TEST_BUCKET, policy_index)

    # Verify template rendering
    mock_templates.TemplateResponse.assert_called_once()
    context = mock_templates.TemplateResponse.call_args[0][2]
    assert context["view"] == "view"
    assert context["edit"] is True
    assert context["policy_detail"] == policy_details


@pytest.mark.asyncio
@patch("objectstore_interface.pages.bucket_pages.create_bucket.templates")
async def test_permissions_page_exception(mock_templates, mock_request):
    """Test the permissions page with exception."""
    # Setup - create a session that raises an exception
    mock_session = MagicMock()
    mock_session.__getitem__.side_effect = Exception("Test exception")
    mock_request.session = mock_session
    mock_templates.TemplateResponse.return_value = MagicMock()

    # Execute
    result = await permissions_page(mock_request, TEST_STORE, TEST_BUCKET)

    # Assert that the page renders despite the error
    mock_templates.TemplateResponse.assert_called_once()

    # Check the template name
    template_name = mock_templates.TemplateResponse.call_args[0][1]
    assert template_name == "bucket_pages/create.html"

    # Verify essential context keys exist
    context = mock_templates.TemplateResponse.call_args[0][2]
    assert "storename" in context
    assert "bucket" in context
    assert "templates" in context


@pytest.mark.asyncio
@patch("objectstore_interface.pages.bucket_pages.create_bucket.storefromjson")
@patch("objectstore_interface.pages.bucket_pages.create_bucket.logging")
@patch("objectstore_interface.pages.bucket_pages.create_bucket.templates")
async def test_create_permissions_exception(
    mock_templates, mock_logging, mock_storefromjson, mock_request, mock_store
):
    """Test permission creation with general exception."""
    # Setup
    mock_storefromjson.return_value = mock_store
    mock_store.create_policy.side_effect = Exception("Test exception")
    mock_templates.TemplateResponse.return_value = MagicMock()

    # Execute
    result = await create_permissions(
        mock_request,
        TEST_STORE,
        TEST_BUCKET,
        actionArray="GetObject",
        application="Users",
        policyName="Test Policy",
        direction="Allow",
        edit="false",
        userNames="user1",
        groupNames="group1",
    )

    # Assert proper error handling
    mock_logging.error.assert_called_once()
    mock_templates.TemplateResponse.assert_called_once_with(
        mock_request, "error.html", {"error": mock.ANY, "advanced": True}
    )


@pytest.mark.asyncio
@patch("objectstore_interface.pages.bucket_pages.create_bucket.storefromjson")
@patch("objectstore_interface.pages.bucket_pages.create_bucket.RedirectResponse")
async def test_template_permissions_client_error(
    mock_redirect, mock_storefromjson, mock_request, mock_store
):
    """Test template permission creation with ClientError."""
    # Setup
    mock_storefromjson.return_value = mock_store
    mock_store.create_policy.side_effect = ClientError(
        {"Error": {"Code": "TestError"}}, "create_policy"
    )
    mock_redirect.return_value = MagicMock()

    # Execute
    result = await template_permissions(
        mock_request, TEST_STORE, TEST_BUCKET, template="read-only-all"
    )

    # Assert proper error handling
    assert mock_request.session["invalid"] is True
    mock_redirect.assert_called_once_with(TEST_CREATE_URL, status_code=303)
