import json
import logging
import sys
import traceback

import jsonpickle
from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from objectstore_interface.object_store_classes.datacore import DataCore
from objectstore_interface.pages.login_pages import login

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()


@router.get("/object-store")
async def object_store_list(request: Request):
    """Gets list of services and figures out which ones are object stores. In future can be used to create different objects for diffent types of store."""
    try:
        try:
            services = await login.oauth.accounts.get(
                f"https://accounts.jasmin.ac.uk/api/services/",
                token=request.session["token"],
            )
        except OAuthError:
            request.session.clear()
            return RedirectResponse("/login")
        services_json = services.json()
        # Only pull entire list when the user has just logged in or there is a change to the users access permissions.
        if request.session.get(
            "user_stores"
        ) == None or services_json != request.session.get("services_json"):
            await login.projects_portal.fetch_token(login.TOKEN_ENDPOINT)
            projects = await login.projects_portal.get(
                f"https://projects.jasmin.ac.uk/api/services/",
                headers={"Accept": "application/json"},
            )
            try:
                services_json["object_store"]
            except KeyError:
                services_json["object_store"] = []
            user_stores = {}
            for service in projects.json():  # Look at each project
                for requirement in service[
                    "requirements"
                ]:  # Look at the requirements for each project
                    if (
                        requirement["resource"]["name"] == "Caringo Object Store HPOS"
                    ):  # See if they're using datacore (caringo) Add more for different object stores (Create class for them as well)
                        if not services_json["object_store"]:
                            pass
                        elif (
                            requirement["location"].split(".")[0]
                            in services_json["object_store"].keys()
                        ):  # Check user has access to this object store
                            user_stores[requirement["location"].split(".")[0]] = {
                                "name": requirement["location"].split(".")[0],
                                "location": requirement["location"],
                            }
                            request.session[
                                requirement["location"].split(".")[0]
                            ] = DataCore(requirement["location"]).toJSON()

            request.session["user_stores"] = user_stores
            request.session["services_json"] = services_json
        else:
            user_stores = request.session["user_stores"]
        return templates.TemplateResponse(
            "object_store_pages/storelist.html",
            {"request": request, "user_stores": user_stores},
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
