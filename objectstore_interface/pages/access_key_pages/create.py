import logging
import sys
import time
import traceback
from typing import Annotated

import jsonpickle
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from objectstore_interface.object_store_classes.base import ObjectStore
from objectstore_interface.object_store_classes.fromjson import storefromjson

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()


@router.get("/object-store/{storename}/create-keys", tags=["create"])
async def create_object_store_keys_page(request: Request, storename):
    """This displays the form for creating keys"""
    try:
        auth_access_key = request.session.get("access_key_" + str(storename), None)

        if not auth_access_key:
            return RedirectResponse(f"/object-store/{storename}")

        return templates.TemplateResponse(
            "access_key_pages/keycreate.html",
            {"request": request, "storename": storename, "view": "create"},
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


@router.post("/object-store/{storename}/create-keys")
async def create_object_store_keys(
    request: Request,
    storename,
    expires: Annotated[str, Form()],
    description: Annotated[str, Form()],
):
    """Takes data from the form and passes it to the objectstore object to create the key.

    Checks that the response is the correct status code and then creates a dictionary so that the page can display the secret and access keys for the user to save.
    """
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])

        response = await object_store.create_key(description, expires)
        if response["status_code"] != 201:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": response["error"]},
                status_code=500,
            )
        else:
            created = {
                "access_key": response["access_key"],
                "secret_key": response["secret_key"],
            }
            # request.session['created'] = created
        # time.sleep(0.5)
        return templates.TemplateResponse(
            "access_key_pages/keycreate.html",
            {
                "request": request,
                "storename": storename,
                "view": "create",
                "created": True,
                "created_dict": created,
            },
        )
        # return templates.TemplateResponse("access_key_pages/keycreate.html", {"request": request, "storename": storename, "view": "create"})
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
