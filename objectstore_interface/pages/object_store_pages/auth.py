import logging
import sys
import traceback
from typing import Annotated

import jsonpickle
from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from objectstore_interface.object_store_classes.base import ObjectStore
from objectstore_interface.object_store_classes.fromjson import storefromjson

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()


@router.get("/object-store/{storename}")
async def object_store_verify_password(request: Request, storename):
    """Checks that the access key exists, if not displays a login page"""
    try:
        timeout = False
        if request.session.get("access_key_" + str(storename)) is not None:
            if request.session.get("timeout") != "true":
                return RedirectResponse(f"/object-store/{storename}/access-keys")
            timeout = True
            request.session.pop("timeout")
        return templates.TemplateResponse(
            "object_store_pages/pass.html",
            {
                "request": request,
                "storename": storename,
                "wrong": "false",
                "timeout": timeout,
            },
        )
    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logging.error(
            "".join(traceback.format_exception(value=exc_value, tb=exc_traceback))
        )
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "".join(
                    traceback.format_exception(value=exc_value, tb=exc_traceback)
                ),
                "advanced": True,
            },
        )


@router.post("/object-store/{storename}")
async def object_store_get_key(
    request: Request, storename, password: Annotated[str, Form()]
):
    """Gets the store access key and adds it to the session"""
    try:
        try:
            object_store: ObjectStore = storefromjson(request.session[storename])
        except KeyError:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error": "".join(
                        traceback.format_exception(value=exc_value, tb=exc_traceback)
                    ),
                    "message": "You do not have access to this store",
                },
            )
        # jsonpickle.decode(request.session[storename])
        response = await object_store.get_access_key(password, request)
        if response["error"] is not None:
            return templates.TemplateResponse(
                "object_store_pages/pass.html",
                {"request": request, "storename": storename, "wrong": "true"},
            )

        request.session["access_key_" + str(storename)] = response["access_key"]
        request.session["s3_access_key_" + str(storename)] = response["s3_access_key"]
        request.session[storename] = object_store.toJSON()
        request.session.pop("timeout", None)
        return RedirectResponse(f"/object-store/{storename}/access-keys", 303)
    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logging.error(
            "".join(traceback.format_exception(value=exc_value, tb=exc_traceback))
        )
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "".join(
                    traceback.format_exception(value=exc_value, tb=exc_traceback)
                ),
                "advanced": True,
            },
        )
