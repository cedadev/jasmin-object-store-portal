from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.httpx_client import AsyncOAuth2Client

templates = Jinja2Templates(directory="templates")

env = Config('.env')
oauth = OAuth()
TOKEN_ENDPOINT = "https://accounts.jasmin.ac.uk/oauth/token/"
SCOPES = ["jasmin.projects.services.all:read"]
oauth.register(
      name='accounts',
      server_metadata_url="https://accounts.jasmin.ac.uk/.well-known/openid-configuration/",
      client_kwargs={"scope": env("accounts_scope")},
      client_id=env("accounts_client_id"),
      client_secret=env("accounts_client_secret")
      )

projects_portal =  AsyncOAuth2Client(
        env("projects_client_id"),
        env("projects_client_secret"),
        scope=" ".join(SCOPES),
)

router = APIRouter()

@router.get("/login")
def login_splash(request: Request):
      return templates.TemplateResponse("login_pages/login.html", {"request": request})


@router.route("/login/redirect")
async def login(request: Request) -> RedirectResponse:
      return await oauth.accounts.authorize_redirect(
            request,
            "http://127.0.0.1:8000/oauth2/redirect",
      )

@router.route("/oauth2/redirect")
async def email(request: Request) -> RedirectResponse:
      request.session["token"] = await oauth.accounts.authorize_access_token(request)
      request.session["projects_token"] = await projects_portal.fetch_token(TOKEN_ENDPOINT, grant_type="client_credentials")
      return RedirectResponse("/object-store" )

@router.get("/account/logout")
async def logout(request: Request):
      request.session.clear()
      return RedirectResponse("/login")
