import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from objectstore_interface.pages.login_pages import login
from objectstore_interface.main import app


# Custom AsyncMock to handle async function mocking
class AsyncMock(MagicMock):
    """Mock class for asynchronous function testing"""

    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


# Test client setup - consider moving to a fixture for better reuse
client = TestClient(app)
mock_token = {"options": {"token": "test-token"}}


@pytest.mark.asyncio
@patch(
    "objectstore_interface.pages.login_pages.login.oauth.accounts",
    new_callable=AsyncMock,
)
async def test_login_redirect(mock_oauth):
    """
    Test that login redirect returns the correct response with proper OAuth parameters.
    Verifies the OAuth flow starts correctly with appropriate prompt settings.
    """
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 302  # Expected redirect status
    mock_oauth.authorize_redirect.return_value = mock_response

    # Execute request
    mock_request = MagicMock()
    response = await login.login(mock_request)

    # Verify OAuth was called with correct parameters
    mock_oauth.authorize_redirect.assert_called_once()
    assert mock_oauth.authorize_redirect.call_args[1]["prompt"] == "login"
    assert response.status_code == 302


@pytest.mark.asyncio
@patch(
    "objectstore_interface.pages.login_pages.login.fetch_tokens", new_callable=AsyncMock
)
async def test_oauth2_callback_success(mock_fetch_tokens):
    """
    Test successful OAuth2 callback flow.
    Verifies:
    1. Tokens are properly fetched from OAuth providers
    2. Tokens are correctly stored in the user session
    3. User is redirected to the main page
    """
    # Setup mock request with query parameters
    mock_request = MagicMock()
    mock_request.url.query = "code=test_code"
    mock_request.session = {}

    # Mock token response from authorization service
    mock_fetch_tokens.return_value = (
        {"access_token": "test_account_token"},
        {"access_token": "test_projects_token"},
    )

    # Execute callback
    response = await login.oauth2_callback(mock_request)

    # Verify tokens were stored in session
    assert mock_request.session["token"] == {"access_token": "test_account_token"}
    assert mock_request.session["projects_token"] == {
        "access_token": "test_projects_token"
    }


@pytest.mark.asyncio
@patch("objectstore_interface.pages.login_pages.login.fetch_tokens")
async def test_oauth2_callback_error(mock_fetch_tokens):
    """
    Test OAuth2 callback error handling.
    Verifies the application correctly handles authentication failures
    and displays appropriate error messages to the user.
    """
    # Setup mock request with no query parameters (invalid state)
    mock_request = MagicMock()
    mock_request.url.query = ""

    # Configure mock to raise an exception when called with no query
    mock_fetch_tokens.side_effect = ValueError(
        "No authorisation code received in redirect"
    )

    # Execute callback and expect error handling
    response = await login.oauth2_callback(mock_request)

    # Verify error template is returned with appropriate error messaging
    assert response.status_code == 200
    response_content = str(response.body)
    assert any(
        message in response_content
        for message in ["Authentication validation failed", "Something went wrong"]
    )


@pytest.mark.asyncio
async def test_logout():
    """
    Test logout functionality.
    Verifies:
    1. Session is properly cleared
    2. User is redirected to the login page
    """
    # Create mock request with session
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_request.session = mock_session

    # Execute logout flow
    response = await login.logout(mock_request)

    # Verify session is cleared and user is redirected
    mock_session.clear.assert_called_once()
    assert response.status_code == 307  # Temporary redirect
    # Could also verify the redirect location if available


@pytest.mark.asyncio
@patch(
    "objectstore_interface.pages.login_pages.login.projects_portal.fetch_token",
    new_callable=AsyncMock,
)
@patch(
    "objectstore_interface.pages.login_pages.login.oauth.accounts.authorize_access_token",
    new_callable=AsyncMock,
)
async def test_fetch_tokens(mock_authorize_access, mock_fetch_token):
    """
    Test token fetching from multiple OAuth providers.
    Verifies tokens are correctly retrieved from both the accounts
    service and the projects portal.
    """
    # Setup mocks with expected return values
    mock_authorize_access.return_value = {"access_token": "test_account_token"}
    mock_fetch_token.return_value = {"access_token": "test_projects_token"}

    # Execute token fetch with mock request
    mock_request = MagicMock()
    account_token, projects_token = await login.fetch_tokens(mock_request)

    # Verify both tokens were fetched with expected values
    assert account_token == {"access_token": "test_account_token"}
    assert projects_token == {"access_token": "test_projects_token"}
    mock_authorize_access.assert_called_once()
    mock_fetch_token.assert_called_once()


@pytest.mark.asyncio
async def test_login_splash():
    """
    Test login splash page rendering.
    Verifies the login page template is properly rendered.
    """
    # Create mock request
    mock_request = MagicMock()

    # Mock templates.TemplateResponse to check template name and context
    with patch(
        "objectstore_interface.pages.login_pages.login.templates"
    ) as mock_templates:
        mock_templates.TemplateResponse.return_value = MagicMock()

        # Execute request
        response = login.login_splash(mock_request)

        # Verify template was rendered with correct name
        mock_templates.TemplateResponse.assert_called_once()
        assert (
            mock_templates.TemplateResponse.call_args[0][1] == "login_pages/login.html"
        )


@pytest.mark.asyncio
async def test_login_splash_exception():
    """
    Test login splash page exception handling.
    Verifies proper error template is returned on exception.
    """
    # Create mock request
    mock_request = MagicMock()

    # Mock templates.TemplateResponse to raise exception on first call but work on second
    with patch(
        "objectstore_interface.pages.login_pages.login.templates"
    ) as mock_templates:
        # First call throws exception
        mock_templates.TemplateResponse.side_effect = [
            Exception("Test error"),
            MagicMock(),
        ]

        # Mock logging to avoid actual error logging
        with patch(
            "objectstore_interface.pages.login_pages.login.logging"
        ) as mock_logging:
            # Execute request which should trigger exception
            response = login.login_splash(mock_request)

            # Verify error was logged
            mock_logging.error.assert_called_once()

            # Verify error template was rendered
            assert mock_templates.TemplateResponse.call_count == 2
            assert mock_templates.TemplateResponse.call_args[0][1] == "error.html"
            # Check error details were included in template context
            assert "advanced" in mock_templates.TemplateResponse.call_args[0][2]
            assert mock_templates.TemplateResponse.call_args[0][2]["advanced"] is True


@pytest.mark.asyncio
@patch("objectstore_interface.pages.login_pages.login.config")
async def test_login_redirect_missing_uri(mock_config):
    """
    Test login redirect with missing redirect URI.
    Verifies proper error handling when redirect_uri is missing from config.
    """
    # Create mock request
    mock_request = MagicMock()

    # Set up config mock to return empty redirect URI
    mock_config.__getitem__.return_value = {"redirectUri": ""}

    # Mock templates for error response verification
    with patch(
        "objectstore_interface.pages.login_pages.login.templates"
    ) as mock_templates:
        mock_templates.TemplateResponse.return_value = MagicMock()

        # Execute request which should trigger error
        response = await login.login(mock_request)

        # Verify error template was rendered with correct message
        mock_templates.TemplateResponse.assert_called_once()
        assert mock_templates.TemplateResponse.call_args[0][1] == "error.html"
        assert "message" in mock_templates.TemplateResponse.call_args[0][2]
        assert (
            mock_templates.TemplateResponse.call_args[0][2]["message"]
            == "Authentication validation failed"
        )
        assert (
            "No redirect URI found in configuration"
            in mock_templates.TemplateResponse.call_args[0][2]["error"]
        )


@pytest.mark.asyncio
@patch("objectstore_interface.pages.login_pages.login.oauth.accounts")
async def test_login_redirect_null_response(mock_oauth_accounts):
    """
    Test login redirect when OAuth returns null response.
    Verifies proper error handling when authorize_redirect returns None.
    """
    # Create mock request
    mock_request = MagicMock()

    # Create an async mock that returns None
    async_mock = AsyncMock()
    async_mock.return_value = None
    mock_oauth_accounts.authorize_redirect = async_mock

    # Mock templates for error response verification
    with patch(
        "objectstore_interface.pages.login_pages.login.templates"
    ) as mock_templates:
        mock_templates.TemplateResponse.return_value = MagicMock()

        # Execute request which should trigger error
        response = await login.login(mock_request)

        # Verify error template was rendered with correct message
        mock_templates.TemplateResponse.assert_called_once()
        assert mock_templates.TemplateResponse.call_args[0][1] == "error.html"
        assert "message" in mock_templates.TemplateResponse.call_args[0][2]
        assert (
            mock_templates.TemplateResponse.call_args[0][2]["message"]
            == "Authentication validation failed"
        )
        assert (
            "Failed to redirect to authorisation endpoint"
            in mock_templates.TemplateResponse.call_args[0][2]["error"]
        )


@pytest.mark.asyncio
@patch("objectstore_interface.pages.login_pages.login.oauth.accounts")
async def test_login_redirect_exception(mock_oauth_accounts):
    """
    Test login redirect general exception handling.
    Verifies proper error template is returned on unexpected exceptions.
    """
    # Create mock request
    mock_request = MagicMock()

    # Configure mock to raise unexpected exception
    mock_oauth_accounts.authorize_redirect.side_effect = Exception(
        "Unexpected OAuth error"
    )

    # Mock logging and templates
    with patch("objectstore_interface.pages.login_pages.login.logging") as mock_logging:
        with patch(
            "objectstore_interface.pages.login_pages.login.templates"
        ) as mock_templates:
            mock_templates.TemplateResponse.return_value = MagicMock()

            # Execute request which should trigger exception
            response = await login.login(mock_request)

            # Verify error was logged
            mock_logging.error.assert_called_once()

            # Verify error template was rendered
            mock_templates.TemplateResponse.assert_called_once()
            assert mock_templates.TemplateResponse.call_args[0][1] == "error.html"
            assert "error" in mock_templates.TemplateResponse.call_args[0][2]
            assert "advanced" in mock_templates.TemplateResponse.call_args[0][2]


@pytest.mark.asyncio
@patch(
    "objectstore_interface.pages.login_pages.login.fetch_tokens", new_callable=AsyncMock
)
async def test_oauth2_callback_no_query(mock_fetch_tokens):
    """
    Test oauth2_callback with no query string.
    Verifies proper error handling when no authorization code is received.
    """
    # Create mock request with empty query
    mock_request = MagicMock()
    mock_request.url.query = ""

    # Mock fetch_tokens to raise the specific ValueError we want to test
    mock_fetch_tokens.side_effect = ValueError(
        "No authorisation code received in redirect"
    )

    # Mock templates for error response verification
    with patch(
        "objectstore_interface.pages.login_pages.login.templates"
    ) as mock_templates:
        mock_templates.TemplateResponse.return_value = MagicMock()

        # Execute callback which should trigger error
        response = await login.oauth2_callback(mock_request)

        # Verify error template was rendered with correct message
        mock_templates.TemplateResponse.assert_called_once()
        assert mock_templates.TemplateResponse.call_args[0][1] == "error.html"
        assert "message" in mock_templates.TemplateResponse.call_args[0][2]
        assert (
            mock_templates.TemplateResponse.call_args[0][2]["message"]
            == "Authentication validation failed"
        )
        assert (
            "No authorisation code received"
            in mock_templates.TemplateResponse.call_args[0][2]["error"]
        )


@pytest.mark.asyncio
@patch("objectstore_interface.pages.login_pages.login.fetch_tokens")
async def test_oauth2_callback_no_tokens(mock_fetch_tokens):
    """
    Test oauth2_callback with missing tokens.
    Verifies proper error handling when tokens cannot be fetched.
    """
    # Create mock request with query parameter
    mock_request = MagicMock()
    mock_request.url.query = "code=test_code"

    # Configure mock to return None for tokens
    mock_fetch_tokens.return_value = (None, None)

    # Mock templates for error response verification
    with patch(
        "objectstore_interface.pages.login_pages.login.templates"
    ) as mock_templates:
        mock_templates.TemplateResponse.return_value = MagicMock()

        # Execute callback which should trigger error
        response = await login.oauth2_callback(mock_request)

        # Verify error template was rendered with correct message
        mock_templates.TemplateResponse.assert_called_once()
        assert mock_templates.TemplateResponse.call_args[0][1] == "error.html"
        assert "message" in mock_templates.TemplateResponse.call_args[0][2]
        assert (
            mock_templates.TemplateResponse.call_args[0][2]["message"]
            == "Authentication validation failed"
        )
        assert (
            "Failed to fetch tokens"
            in mock_templates.TemplateResponse.call_args[0][2]["error"]
        )


@pytest.mark.asyncio
async def test_logout_exception():
    """
    Test logout exception handling.
    Verifies proper error template is returned when logout fails.
    """
    # Create mock request with session that raises exception on clear()
    mock_request = MagicMock()
    mock_request.session.clear.side_effect = Exception("Session clear error")

    # Mock logging and templates
    with patch("objectstore_interface.pages.login_pages.login.logging") as mock_logging:
        with patch(
            "objectstore_interface.pages.login_pages.login.templates"
        ) as mock_templates:
            mock_templates.TemplateResponse.return_value = MagicMock()

            # Execute logout which should trigger exception
            response = await login.logout(mock_request)

            # Verify error was logged
            mock_logging.error.assert_called_once()

            # Verify error template was rendered
            mock_templates.TemplateResponse.assert_called_once()
            assert mock_templates.TemplateResponse.call_args[0][1] == "error.html"
            assert "error" in mock_templates.TemplateResponse.call_args[0][2]
            assert "advanced" in mock_templates.TemplateResponse.call_args[0][2]
