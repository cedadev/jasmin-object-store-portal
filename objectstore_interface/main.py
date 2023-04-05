from typing import Annotated
import requests as r

import jsonpickle
from requests.auth import HTTPBasicAuth
import time
from object_store_classes.base import ObjectStore
from object_store_classes.datacore import DataCore
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.httpx_client import AsyncOAuth2Client, OAuth2Auth
from starlette.config import Config
from starlette.middleware import Middleware, sessions
from datetime import datetime
from dateutil.relativedelta import relativedelta
from custom_middleware import RedirectWhenLoggedOut

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

print(env("projects_scope"))
projects_portal =  AsyncOAuth2Client(
        env("projects_client_id"),
        env("projects_client_secret"),
        scope=" ".join(SCOPES),
)


templates = Jinja2Templates(directory="templates")

middleware = [
      Middleware(
            sessions.SessionMiddleware,
            secret_key="supersecret",
      ),
      Middleware(
            RedirectWhenLoggedOut
      ),
]

app = FastAPI(middleware=middleware)

app.mount("/static", StaticFiles(directory="static"), name="static")

async def get_key_list(request: Request, url, auth_access_key) -> r.Response:
      headers = {
            'Cookie': 'token=' + auth_access_key,
      }

      response = r.get(
            f"{url}:81/.TOKEN/?format=json",
            headers=headers
      )

      return response

@app.route("/")
def root(request: Request):
      return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
def login_splash(request: Request):
      return templates.TemplateResponse("login.html", {"request": request})

@app.get("/object-store")
async def object_store_list(request: Request):
      services = await oauth.accounts.get(f"https://accounts.jasmin.ac.uk/api/services/", token=request.session["token"])
      services_json = services.json()

      # Only pull entire list when the user has just logged in or there is a change to the users access permissions.
      if request.session.get("user_stores") == None or services_json != request.session.get("services_json"):
            await projects_portal.fetch_token(TOKEN_ENDPOINT)
            projects = await projects_portal.get(f"https://projects.jasmin.ac.uk/api/services/", headers={"Accept": "application/json"})
            user_stores = {}
            for service in projects.json():
                  for requirement in service["requirements"]:
                        if requirement["resource"]["name"] == "Caringo Object Store HPOS":
                              if requirement["location"].split(".")[0] in services_json["object_store"].keys():
                                    user_stores[requirement["location"].split(".")[0]] = {"name": requirement["location"].split(".")[0], "location": requirement["location"]}
                                    request.session[requirement["location"].split(".")[0]] = jsonpickle.encode(DataCore(requirement["location"]))

            request.session["user_stores"] = user_stores
            request.session["services_json"] = services_json
      else:
            user_stores = request.session["user_stores"]
      return templates.TemplateResponse("storelist.html", {"request": request, "user_stores": user_stores})

@app.route("/login/redirect")
async def login(request: Request) -> RedirectResponse:
      return await oauth.accounts.authorize_redirect(
            request,
            "http://127.0.0.1:8000/oauth2/redirect",
      )

@app.route("/oauth2/redirect")
async def email(request: Request) -> RedirectResponse:
      request.session["token"] = await oauth.accounts.authorize_access_token(request)
      request.session["projects_token"] = await projects_portal.fetch_token(TOKEN_ENDPOINT, grant_type="client_credentials")
      return RedirectResponse("/object-store" )

@app.get("/object-store/{storename}")
async def object_store_verify_password(request: Request, storename):
      if request.session.get("token") is not None:
            if request.session.get('access_key_' + str(storename)) is not None:
                  return RedirectResponse(f"/object-store/{storename}/access-keys")
            return templates.TemplateResponse("pass.html", {"request": request, "storename": storename})
      return RedirectResponse("/login")

@app.post("/object-store/{storename}")
async def object_store_get_key(request: Request, storename, password: Annotated[str, Form()]) -> HTMLResponse:
      object_store: ObjectStore = jsonpickle.decode(request.session[storename])
      response = await object_store.get_access_key(password, request)
      if response["error"] is not None:
            return templates.TemplateResponse("error.html", {"request": request, "error": response["error"]})

      request.session['access_key_' + str(storename)] = response["access_key"]
      request.session[storename] = jsonpickle.encode(object_store)
      return RedirectResponse(f"/object-store/{storename}/access-keys")

@app.get("/object-store/{storename}/access-keys")
async def object_store_show_details(request: Request, storename: str):
      object_store: ObjectStore = jsonpickle.decode(request.session[storename])
      auth_access_key = request.session.get('access_key_' + str(storename), None)

      if not auth_access_key:
            return RedirectResponse(f"/object-store/{storename}")

      # Set the request headers.
      
      response = await object_store.get_store(request)

      if response["status_code"] == 401:
            del request.session['access_key_' + str(storename)]
            return RedirectResponse(f"/object-store/{storename}")

      if response["status_code"] != 200:
            return templates.TemplateResponse("error.html", {"request": request, "error": f"{response.status_code}: {response.text}"})


      return templates.TemplateResponse("access_key_pages/objectstore.html", {"request": request, "access_keys": response["access_keys"], "storename": storename, "view": "view"})

@app.post("/object-store/{storename}/access-keys")
async def access_key_delete(request: Request, storename: str, delete_access_key: Annotated[str, Form()] = None):
      object_store: ObjectStore = jsonpickle.decode(request.session[storename])
      if delete_access_key != None:
            # Set the request headers
            response = await object_store.delete_key(delete_access_key)

            if response["status_code"] == 400:
                  return RedirectResponse(f"/object-store/{storename}/access-keys", 303)
            if response["status_code"] != 200:
                  return templates.TemplateResponse("error.html", {"request": request, "error": response["error"]})

            time.sleep(1) # Give object store server time to update
            return RedirectResponse(f"/object-store/{storename}/access-keys", 303)
      else:
            return RedirectResponse(f"/object-store/{storename}/access-keys", 303)

@app.get("/object-store/{storename}/create-keys")
async def create_object_store_keys_page(request: Request, storename):
      object_store_url = f"http://{storename}.s3.jc.rl.ac.uk"
      auth_access_key = request.session.get('access_key_' + str(storename), None)

      if not auth_access_key:
            return RedirectResponse(f"/object-store/{storename}")
      
      return templates.TemplateResponse("access_key_pages/keycreate.html", {"request": request, "storename": storename, "view": "create"})

@app.post("/object-store/{storename}/create-keys")
async def create_object_store_keys(request: Request, storename, expires: Annotated[str, Form()], description: Annotated[str, Form()]):
      object_store: ObjectStore = jsonpickle.decode(request.session[storename])
      
      response = await object_store.create_key(description, expires)

      if response["status_code"] != 201:
            return templates.TemplateResponse("error.html", {"request": request, "error": response["error"]})
      else:
            created = {
                  'access_key': response["access_key"],
                  'secret_key': response["secret_key"],
            }
            request.session['created'] = created
      return templates.TemplateResponse("access_key_pages/keycreate.html", {"request": request, "storename": storename, "view": "create", "created": True})



@app.get("/account/logout")
async def logout(request: Request):
      request.session.clear()
      return RedirectResponse("/login")

      
