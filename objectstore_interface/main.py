from objectstore_interface.pages.access_key_pages import view, create, bucket
from objectstore_interface.pages.login_pages import login
from objectstore_interface.pages.object_store_pages import auth, list
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware, sessions
import yaml
import logging
from objectstore_interface.custom_middleware import RedirectWhenLoggedOut, MockSessionMiddleware
from starsessions import InMemoryStore, SessionMiddleware, SessionAutoloadMiddleware

templates = Jinja2Templates(directory="objectstore_interface/templates")
with open("conf/common.secrets.yaml") as confile:
      config = yaml.safe_load(confile)

session_store = InMemoryStore()

middleware = [
      Middleware(
            SessionMiddleware,
            store = session_store,
            lifetime=3600*24*14
      ),
      Middleware(SessionAutoloadMiddleware),
      Middleware(
            RedirectWhenLoggedOut
      ),
]

if config["testing"] == True:
      middleware.insert(1, Middleware(MockSessionMiddleware))

app = FastAPI(middleware=middleware)

app.mount("/static", StaticFiles(directory="objectstore_interface/static"), name="static")

app.include_router(view.router)
app.include_router(create.router)
app.include_router(login.router)
app.include_router(auth.router)
app.include_router(list.router)
app.include_router(bucket.router)

@app.route("/")
def root(request: Request):
      try:
            return templates.TemplateResponse("index.html", {"request": request})
      except Exception as e:
        logging.error(e)
        return templates.TemplateResponse("error.html", {"error": e})
