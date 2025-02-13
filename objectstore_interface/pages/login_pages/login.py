from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import yaml
import logging, traceback, sys
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.httpx_client import AsyncOAuth2Client
from tenacity import retry, stop_after_attempt, wait_exponential

templates = Jinja2Templates(directory="objectstore_interface/templates")

with open("conf/common.secrets.yaml") as confile:
    config = yaml.safe_load(confile)
oauth = OAuth()
TOKEN_ENDPOINT = "https://accounts.jasmin.ac.uk/oauth/token/"
SCOPES = ["jasmin.projects.services.all:read"]
try:
    oauth.register(
        name="accounts",
        server_metadata_url="https://accounts.jasmin.ac.uk/.well-known/openid-configuration/",
        client_kwargs={"scope": config["accounts"]["scope"]},
        client_id=config["accounts"]["client_id"],
        client_secret=config["accounts"]["client_secret"],
    )
except KeyError:
    exit()

projects_portal = AsyncOAuth2Client(
    config["projects"]["client_id"],
    config["projects"]["client_secret"],
    scope=config["projects"]["scope"],  # " ".join(SCOPES),
    timeout=30,
)

router = APIRouter()


@router.get("/login")
def login_splash(request: Request):
    """Displays the login page"""
    try:
        return templates.TemplateResponse(
            "login_pages/login.html", {"request": request}
        )
    except Exception as exc:

        logging.error("".join(traceback.format_exception(exc)))
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "".join(traceback.format_exception(exc)),
                "advanced": True,
            },
        )


@router.route("/login/redirect")
async def login(request: Request) -> RedirectResponse:
    """Starts the authorisation process"""
    try:
        redirect_uri = config["accounts"]["redirectUri"]

        if not redirect_uri:
            raise ValueError("No redirect URI found in configuration")

        response = await oauth.accounts.authorize_redirect(
            request, redirect_uri, prompt="login"
        )

        if not response or response.status_code != 307:
            raise ValueError("Failed to redirect to authorisation endpoint")

        return response

    except ValueError as ve:
        logging.error(f"Validation error : {str(ve)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Authentication validation failed",
                "error": str(ve),
                "advanced": True,
            },
        )
    except Exception as exc:
        logging.error("".join(traceback.format_exception(exc)))
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "".join(traceback.format_exception(exc)),
                "advanced": True,
            },
        )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplies=1, min=4, max=10),
    reraise=True,
)
async def fetch_tokens(request: Request):
    account_token = await oauth.accounts.authorizr_access_token(request)
    projects_token = await projects_portal.fetch_token(
        TOKEN_ENDPOINT, grant_type="client_credentials"
    )

    return account_token, projects_token


@router.route("/oauth2/redirect")
async def email(request: Request) -> RedirectResponse:
    """Creates the token and adds it to the session"""
    try:
        account_token, projects_token = await fetch_tokens(request)

        if not request.url.query:
            raise ValueError("No authorisation code received in redirect")

        if not account_token or not projects_token:
            raise ValueError("Failed to fetch tokens")

        return RedirectResponse("/object-store")

    except ValueError as ve:
        logging.error(f"Validation error: {str(ve)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Authentication validation failed",
                "error": str(ve),
                "advanced": True,
            },
        )
    except Exception as exc:

        logging.error("".join(traceback.format_exception(exc)))
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "".join(traceback.format_exception(exc)),
                "advanced": True,
            },
        )


@router.get("/account/logout")
async def logout(request: Request):
    """Clears the current session"""
    try:
        request.session.clear()
        return RedirectResponse("/login")
    except Exception as exc:

        logging.error("".join(traceback.format_exception(exc)))
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "".join(traceback.format_exception(exc)),
                "advanced": True,
            },
        )
