import logging
import sys
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from objectstore_interface.object_store_classes.base import ObjectStore
from objectstore_interface.object_store_classes.fromjson import storefromjson

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()


@router.get("/object-store/{storename}/buckets")
async def view_buckets(request: Request, storename):
    """Displays the list of buckets"""
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])
        try:
            bucket_list = await object_store.get_buckets()
        except Exception as exc:

            logging.error("".join(traceback.format_exception(exc)))
            request.session["timeout"] = "true"
            return RedirectResponse(f"/object-store/{storename}")
        return templates.TemplateResponse(
            "access_key_pages/buckets.html",
            {
                "request": request,
                "storename": storename,
                "view": "buckets",
                "buckets": bucket_list,
            },
        )
    except Exception as exc:

        logging.error("".join(traceback.format_exception(exc)))
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "".join(traceback.format_exception(exc)),
                "advanced": True,
            },
        )
