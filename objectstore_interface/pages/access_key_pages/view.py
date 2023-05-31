import jsonpickle
import time
import logging, traceback, sys
from objectstore_interface.object_store_classes.base import ObjectStore
from objectstore_interface.object_store_classes.fromjson import storefromjson
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()

@router.get("/object-store/{storename}/access-keys")
async def object_store_show_details(request: Request, storename: str):
      try:
            object_store: ObjectStore = storefromjson(request.session[storename])
            auth_access_key = request.session.get('access_key_' + str(storename), None)
            if request.session.get('created'):
                  request.session.pop('created')

            if not auth_access_key:
                  return RedirectResponse(f"/object-store/{storename}")

            response = await object_store.get_store(request)
            if response["status_code"] == 401:
                  del request.session['access_key_' + str(storename)]
                  return RedirectResponse(f"/object-store/{storename}")

            if response["status_code"] != 200:
                  return templates.TemplateResponse("error.html", {"request": request, "error": f"{response.status_code}: {response.text}"})

            return templates.TemplateResponse("access_key_pages/objectstore.html", {"request": request, "access_keys": response["access_keys"], "storename": storename, "view": "view"})
      except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error("".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)))
            return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)), "advanced": True})

@router.post("/object-store/{storename}/access-keys")
async def access_key_delete(request: Request, storename: str, delete_access_key: Annotated[str, Form()]):
      try:
            object_store: ObjectStore = storefromjson(request.session[storename])
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
                  logging.error(e)
                  return RedirectResponse(f"/object-store/{storename}/access-keys", 303)
      except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error("".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)))
            return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)), "advanced": True})
