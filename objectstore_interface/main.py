from typing import Annotated
import requests as r
import random
import string
from requests.auth import HTTPBasicAuth
import time
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from authlib.integrations.starlette_client import OAuth
import  authlib.integrations.httpx_client
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
projects_portal = authlib.integrations.httpx_client.AsyncOAuth2Client(
        env("projects_client_id"),
        env("projects_client_secret"),
        scope=" ".join(SCOPES),
        # Don't use verify=False in production!!
        verify=False,
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
def object_store_list(request: Request):
      return templates.TemplateResponse("storelist.html", {"request": request})

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

@app.get("/jasmin")
async def jasmin(request: Request) -> HTMLResponse:
      response = await oauth.accounts.get(f"https://accounts.jasmin.ac.uk/api/v1/", token=request.session["token"])
      return  JSONResponse(response.json())

@app.get("/jasmin/{endpoint}")
async def jasmin_endpoint(request: Request, endpoint) -> HTMLResponse:
      response = await oauth.accounts.get(f"https://accounts.jasmin.ac.uk/api/{endpoint}/", token=request.session["token"])
      return  JSONResponse(response.json())

@app.get("/jasmin/{endpoint}/{detail}")
async def jasmin_detail(request: Request, endpoint, detail) -> HTMLResponse:
      response = await oauth.accounts.get(f"https://accounts.jasmin.ac.uk/api/{endpoint}/{detail}/", token=request.session["token"])
      return  JSONResponse(response.json())

@app.get("/object-store/{storename}")
async def object_store_verify_password(request: Request, storename):
      if request.session.get("token") is not None:
            if request.session.get('access_key_' + str(storename)) is not None:
                  return RedirectResponse(f"/object-store/{storename}/access-keys")
            return templates.TemplateResponse("pass.html", {"request": request, "storename": storename})
      return RedirectResponse("/login")

@app.post("/object-store/{storename}")
async def object_store_get_key(request: Request, storename, password: Annotated[str, Form()]) -> HTMLResponse:
      object_store_url = f"http://{storename}.s3.jc.rl.ac.uk"
      response = r.get(f"{object_store_url}:81/.TOKEN/?format=json", auth=HTTPBasicAuth(request.session["token"]["userinfo"]["preferred_username"], password))
      if response.status_code != 200:
            return templates.TemplateResponse("error.html", {"request": request, "error": f"{response.status_code}: {response.content.strip()}"})
      auth_access_keys = [ak for ak in response.json() if ak['x_custom_meta_source'] == "JASMIN account auth access key"]

      auth_access_key_name = False
      for auth_access_key in auth_access_keys:
            print(auth_access_key)
            lifepoint = datetime.strptime(auth_access_key['lifepoint'].split(']')[0], '[%a, %d %b %Y %H:%M:%S %Z')
            if lifepoint > datetime.today():
                  auth_access_key_name = auth_access_key['name']

      # If no unexpired auth access key exists, create one.
      if not auth_access_key_name:
            expires = datetime.today() + relativedelta(weeks = 1)
            headers = {
                  'X-Custom-Meta-Source': 'JASMIN account auth access key',
                  'X-User-Token-Expires-Meta': expires.strftime('%Y-%m-%d'),
            }
            url = object_store_url + ':81/.TOKEN/?format=json'
            response = r.post(
                  url,
                  headers=headers,
                  auth=HTTPBasicAuth(request.session["token"]["userinfo"]["preferred_username"], password)
            )
            auth_access_key_name = response.text.split()[1]

            # Put the auth access key in the session. Add service id to name to make unique, 
            # as users could have multiple auth access keys (one for each of their services).
      request.session['access_key_' + str(storename)] = auth_access_key_name
      return RedirectResponse(f"/object-store/{storename}/access-keys")

@app.get("/object-store/{storename}/access-keys")
async def object_store_show_details(request: Request, storename: str):
      object_store_url = f"http://{storename}.s3.jc.rl.ac.uk"
      auth_access_key = request.session.get('access_key_' + str(storename), None)

      if not auth_access_key:
            return RedirectResponse(f"/object-store/{storename}")

      # Set the request headers.
      
      response = await get_key_list(request, object_store_url, auth_access_key)

      if response.status_code == 401:
            del request.session['access_key_' + str(storename)]
            return RedirectResponse(f"/object-store/{storename}")

      if response.status_code != 200:
            return templates.TemplateResponse("error.html", {"request": request, "error": f"{response.status_code}: {response.text}"})


      return templates.TemplateResponse("access_key_pages/objectstore.html", {"request": request, "access_keys": response.json(), "storename": storename, "view": "view"})

@app.post("/object-store/{storename}/access-keys")
async def access_key_delete(request: Request, storename: str, delete_access_key: Annotated[str, Form()] = None):
      object_store_url = f"http://{storename}.s3.jc.rl.ac.uk"
      auth_access_key = request.session.get('access_key_' + str(storename), None)
      if delete_access_key != None:
            # Set the request headers.
            headers = {
                  'Cookie': 'token=' + auth_access_key,
            }

            url = object_store_url + ':81/.TOKEN/' + delete_access_key
            response = r.delete(
            url,
            headers=headers,
            )
            if response.status_code == 400:
                  return RedirectResponse(f"/object-store/{storename}/access-keys", 303)
            if response.status_code != 200:
                  return {"Error": response.content.strip(), "status_code": response.status_code}

            time.sleep(0.25) # Give object store server time to update
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
      object_store_url = f"http://{storename}.s3.jc.rl.ac.uk"
      auth_access_key = request.session.get('access_key_' + str(storename), None)
      secret_key = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=64))
      headers = {
            'X-User-Secret-Key_meta': secret_key,
            'X-Custom-Meta-Source': description,
            'X-User-Token-Expires-Meta': expires,
            'Cookie': 'token=' + auth_access_key,
      }
      url = object_store_url + ":81/.TOKEN/"

      response = r.post(
            url,
            headers=headers,
      )

      response_text = response.text

      if response.status_code != 201:
            return templates.TemplateResponse("error.html", {"request": request, "error": f"{response.status_code}: {response_text}"})
      else:
            created = {
                  'access_key': response_text.split()[1],
                  'secret_key': secret_key,
            }
            request.session['created'] = created
      return templates.TemplateResponse("access_key_pages/keycreate.html", {"request": request, "storename": storename, "view": "create", "created": True})



@app.get("/account/logout")
async def logout(request: Request):
      request.session.clear()
      return RedirectResponse("/login")

      
