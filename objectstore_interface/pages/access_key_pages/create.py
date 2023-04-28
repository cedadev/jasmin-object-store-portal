import jsonpickle
import time

from objectstore_interface.object_store_classes.base import ObjectStore
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()

@router.get("/object-store/{storename}/create-keys", tags=["create"])
async def create_object_store_keys_page(request: Request, storename):
      auth_access_key = request.session.get('access_key_' + str(storename), None)

      if not auth_access_key:
            return RedirectResponse(f"/object-store/{storename}")
      
      return templates.TemplateResponse("access_key_pages/keycreate.html", {"request": request, "storename": storename, "view": "create"})

@router.post("/object-store/{storename}/create-keys")
async def create_object_store_keys(request: Request, storename, expires: Annotated[str, Form()], description: Annotated[str, Form()]):
      object_store: ObjectStore = jsonpickle.decode(request.session[storename])
      
      response = await object_store.create_key(description, expires)
      if response["status_code"] != 201:
            return templates.TemplateResponse("error.html", {"request": request, "error": response["error"]}, status_code=500)
      else:
            created = {
                  'access_key': response["access_key"],
                  'secret_key': response["secret_key"],
            }
            request.session['created'] = created
      time.sleep(0.5)
      return templates.TemplateResponse("access_key_pages/keycreate.html", {"request": request, "storename": storename, "view": "create", "created": True}, status_code=201)
