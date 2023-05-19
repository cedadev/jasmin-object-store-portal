import jsonpickle
import logging
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from objectstore_interface.object_store_classes.datacore import DataCore
from objectstore_interface.pages.login_pages import login

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()

@router.get("/object-store")
async def object_store_list(request: Request):
      try:
            services = await login.oauth.accounts.get(f"https://accounts.jasmin.ac.uk/api/services/", token=request.session["token"])
            services_json = services.json()

            # Only pull entire list when the user has just logged in or there is a change to the users access permissions.
            if request.session.get("user_stores") == None or services_json != request.session.get("services_json"):
                  await login.projects_portal.fetch_token(login.TOKEN_ENDPOINT)
                  projects = await login.projects_portal.get(f"https://projects.jasmin.ac.uk/api/services/", headers={"Accept": "application/json"})
                  user_stores = {}
                  for service in projects.json(): #Look at each project
                        for requirement in service["requirements"]: # Look at the requirements for each project
                              logging.debug(requirement["resource"]["name"])
                              if requirement["resource"]["name"] == "Caringo Object Store HPOS": #See if they're using datacore (caringo) Add more for different object stores (Create class for them as well)
                                    if requirement["location"].split(".")[0] in services_json["object_store"].keys(): #Check user has access to this object store
                                          user_stores[requirement["location"].split(".")[0]] = {"name": requirement["location"].split(".")[0], "location": requirement["location"]}
                                          request.session[requirement["location"].split(".")[0]] = jsonpickle.encode(DataCore(requirement["location"]))

                  request.session["user_stores"] = user_stores
                  request.session["services_json"] = services_json
            else:
                  user_stores = request.session["user_stores"]
            return templates.TemplateResponse("object_store_pages/storelist.html", {"request": request, "user_stores": user_stores})
      except Exception as e:
        logging.error(e)
        return templates.TemplateResponse("error.html", {"error": e})