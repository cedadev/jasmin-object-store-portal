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
        # Check if user already has an access key for this store in their session
        if request.session.get("access_key_" + str(storename)) is not None:
            # If no timeout has occurred, redirect to access keys page
            if request.session.get("timeout") != "true":
                return RedirectResponse(f"/object-store/{storename}/access-keys")
            timeout = True
            request.session.pop("timeout")
        return templates.TemplateResponse(
            request,
            "object_store_pages/pass.html",
            {
                "storename": storename,
                "wrong": "false",
                "timeout": timeout,
            },
        )
    except Exception as exc:

        logging.error("".join(traceback.format_exception(exc)))
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "error": "".join(traceback.format_exception(exc)),
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
            # Retrieve the object store instance from the session
            object_store: ObjectStore = storefromjson(request.session[storename])
        except KeyError:
            # If storename not in session, user doesn't have access to this store
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "error": f"You do not have access to the store {storename}",
                    "message": "You do not have access to this store",
                },
            )
        # Use password to retrieve access key from the object store
        response = await object_store.get_access_key(password, request)
        # If there's an error, show the password form again
        if response["error"] is not None:
            return templates.TemplateResponse(
                request,
                "object_store_pages/pass.html",
                {"storename": storename, "wrong": "true"},
            )
        # Store the retrieved access keys in the session
        request.session["access_key_" + str(storename)] = response["access_key"]
        request.session["s3_access_key_" + str(storename)] = response["s3_access_key"]
        request.session[storename] = object_store.toJSON()
        request.session.pop("timeout", None)
        # Redirect to access keys page
        return RedirectResponse(f"/object-store/{storename}/access-keys", 303)
    except Exception as exc:

        logging.error("".join(traceback.format_exception(exc)))
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "error": "".join(traceback.format_exception(exc)),
                "advanced": True,
            },
        )
