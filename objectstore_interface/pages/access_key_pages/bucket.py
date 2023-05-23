import jsonpickle
import logging, traceback
from objectstore_interface.object_store_classes.base import ObjectStore
from objectstore_interface.object_store_classes.fromjson import storefromjson
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()

@router.get("/object-store/{storename}/buckets")
async def view_buckets(request: Request, storename):
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])

        bucket_list = await object_store.get_buckets()
        return  JSONResponse(bucket_list)
    #templates.TemplateResponse("access_key_pages/buckets.html", {"request": request, "storename": storename, "view": "buckets", "buckets": bucket_list})
    except Exception as e:
        logging.error("".join(traceback.format_exc(e)))
        return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exc(e))})

@router.get("/object-store/{storename}/buckets/{bucket}/policy")
async def view_permissions(request: Request, storename, bucket):
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])

        perm_list = await object_store.get_bucket_details(bucket)

        return templates.TemplateResponse("bucket_pages/policies.html", {"request": request, "view": "view", "policy": perm_list, "storename": storename, "bucket": bucket})
    except Exception as e:
        logging.error("".join(traceback.format_exc(e)))
        return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exc(e))})

@router.post("/object-store/{storename}/buckets/{bucket}/policy")
async def delete_policy(request: Request, storename, bucket, policy: Annotated[str, Form()]):
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])
        detail = policy.split("_")
        if detail[0] == "delete":
            response = await object_store.delete_policy(bucket, detail[1])

            return RedirectResponse(f"/object-store/{storename}/buckets/{bucket}/policy", status_code=303)
        if detail[0] == "edit":
            return "Edit"
    except Exception as e:
        logging.error("".join(traceback.format_exc(e)))
        return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exc(e))})

@router.get("/object-store/{storename}/buckets/{bucket}/create")
async def permissions_page(request: Request, storename, bucket):
    try:
        return templates.TemplateResponse("bucket_pages/create.html", {"request": request, "view": "create", "storename": storename, "bucket": bucket})
    except Exception as e:
        logging.error("".join(traceback.format_exc(e)))
        return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exc(e))})

@router.post("/object-store/{storename}/buckets/{bucket}/create")
async def create_permissions(
                            request: Request, 
                            storename, bucket, 
                            actionArray: Annotated[str, Form()], 
                            application: Annotated[str, Form()], 
                            userNames: Annotated[str, Form()], 
                            groupNames: Annotated[str, Form()],
                            policyName: Annotated[str, Form()],
                            direction: Annotated[str, Form()]
):
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])
        response = await object_store.create_policy(actionArray, groupNames, userNames, application, policyName, direction, bucket)

        return RedirectResponse(f"/object-store/{storename}/buckets/{bucket}/policy", status_code=303)
    except Exception as e:
        logging.error("".join(traceback.format_exc(e)))
        return templates.TemplateResponse("error.html", {"request": request, "error": "".join(traceback.format_exc(e))})