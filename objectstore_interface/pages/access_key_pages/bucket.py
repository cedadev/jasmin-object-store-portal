import logging, traceback, sys
from objectstore_interface.object_store_classes.base import ObjectStore
from objectstore_interface.object_store_classes.fromjson import storefromjson
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()

@router.get("/object-store/{storename}/buckets")
async def view_buckets(request: Request, storename):
    """Displays the list of buckets"""
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])
        try:
            bucket_list = await object_store.get_buckets()
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error("".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)))
            request.session["timeout"] = "true"
            return RedirectResponse(f"/object-store/{storename}")
        return  templates.TemplateResponse("access_key_pages/buckets.html", {"request": request, "storename": storename, "view": "buckets", "buckets": bucket_list})
    except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error("".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)))
            return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exception(etype=exc_type, value=exc_value, tb=exc_traceback)), "advanced": True})
