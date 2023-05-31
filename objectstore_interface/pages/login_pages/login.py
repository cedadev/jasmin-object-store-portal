from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import yaml
import logging, traceback, sys
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.httpx_client import AsyncOAuth2Client

templates = Jinja2Templates(directory="objectstore_interface/templates")

with open("conf/common.secrets.yaml") as confile:
      config = yaml.safe_load(confile)
oauth = OAuth()
TOKEN_ENDPOINT = "https://accounts.jasmin.ac.uk/oauth/token/"
SCOPES = ["jasmin.projects.services.all:read"]
try:
      oauth.register(
            name='accounts',
            server_metadata_url="https://accounts.jasmin.ac.uk/.well-known/openid-configuration/",
            client_kwargs={"scope": config["accounts"]["scope"]},
            client_id=config["accounts"]["client_id"],
            client_secret=config["accounts"]["client_secret"]
            )
except KeyError:
      exit()

projects_portal =  AsyncOAuth2Client(
        config["projects"]["client_id"],
        config["projects"]["client_secret"],
        scope=config["projects"]["scope"], #" ".join(SCOPES),
)

router = APIRouter()

@router.get("/login")
def login_splash(request: Request):
      try:
            return templates.TemplateResponse("login_pages/login.html", {"request": request})
      except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error("".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)))
            return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)), "advanced": True})


@router.route("/login/redirect")
async def login(request: Request) -> RedirectResponse:
      try:
            return await oauth.accounts.authorize_redirect(
                  request,
                  config["accounts"]["redirectUri"],
            )
      except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error("".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)))
            return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)), "advanced": True})

@router.route("/oauth2/redirect")
async def email(request: Request) -> RedirectResponse:
      try:
            request.session["token"] = await oauth.accounts.authorize_access_token(request)
            request.session["projects_token"] = await projects_portal.fetch_token(TOKEN_ENDPOINT, grant_type="client_credentials")
            return RedirectResponse("/object-store" )
      except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error("".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)))
            return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)), "advanced": True})

@router.get("/account/logout")
async def logout(request: Request):
      try:
            request.session.clear()
            return RedirectResponse("/login")
      except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error("".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)))
            return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)), "advanced": True})
