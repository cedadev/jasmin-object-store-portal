import jsonpickle

from objectstore_interface.object_store_classes.base import ObjectStore
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()


@router.get("/object-store/{storename}")
async def object_store_verify_password(request: Request, storename):
      if request.session.get('access_key_' + str(storename)) is not None:
            return RedirectResponse(f"/object-store/{storename}/access-keys")
      return templates.TemplateResponse("object_store_pages/pass.html", {"request": request, "storename": storename})

@router.post("/object-store/{storename}")
async def object_store_get_key(request: Request, storename, password: Annotated[str, Form()]):
      object_store: ObjectStore = jsonpickle.decode(request.session[storename])
      response = await object_store.get_access_key(password, request)
      if response["error"] is not None:
            return templates.TemplateResponse("error.html", {"request": request, "error": response["error"]})

      request.session['access_key_' + str(storename)] = response["access_key"]
      request.session['s3_access_key_' + str(storename)] = response["s3_access_key"]
      request.session[storename] = jsonpickle.encode(object_store)
      return RedirectResponse(f"/object-store/{storename}/access-keys", 303)
      