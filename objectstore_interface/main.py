from pages.access_key_pages import view, create
from pages.login_pages import login
from pages.object_store_pages import auth, list
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware, sessions
from custom_middleware import RedirectWhenLoggedOut

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

app.include_router(view.router)
app.include_router(create.router)
app.include_router(login.router)
app.include_router(auth.router)
app.include_router(list.router)

@app.route("/")
def root(request: Request):
      return templates.TemplateResponse("index.html", {"request": request})
