import logging, traceback, sys
from objectstore_interface.object_store_classes.base import ObjectStore
from objectstore_interface.object_store_classes.fromjson import storefromjson
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated
from botocore.exceptions import ClientError

templates = Jinja2Templates(directory="objectstore_interface/templates")

router = APIRouter()


@router.get("/object-store/{storename}/buckets/{bucket}/policy")
async def view_permissions(request: Request, storename, bucket):
    """Displays the list of permissions"""
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])
        try:
            perm_list = await object_store.get_bucket_details(bucket)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error(
                "".join(traceback.format_exception(value=exc_value, tb=exc_traceback))
            )
            request.session["timeout"] = "true"
            return RedirectResponse(f"/object-store/{storename}")
        invalid = request.session.pop("invalid", False)
        return templates.TemplateResponse(
            "bucket_pages/policies.html",
            {
                "request": request,
                "view": "view",
                "policy": perm_list,
                "storename": storename,
                "bucket": bucket,
                "edit": False,
                "invalid": invalid,
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


@router.post("/object-store/{storename}/buckets/{bucket}/policy")
async def delete_policy(
    request: Request, storename, bucket, policy: Annotated[str, Form()]
):
    """Calls the delete_policy function and then redirects to the GET version of this page."""
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])
        detail = policy.split("_")
        if detail[0] == "delete":
            response = await object_store.delete_policy(bucket, detail[1])

            return RedirectResponse(
                f"/object-store/{storename}/buckets/{bucket}/policy", status_code=303
            )
        if detail[0] == "edit":
            detail = policy.split("_")

            perm_list = await object_store.get_bucket_details(bucket)

            policy_details = await object_store.get_individual_policy(bucket, detail[1])

            return templates.TemplateResponse(
                "bucket_pages/policies.html",
                {
                    "request": request,
                    "view": "view",
                    "policy": perm_list,
                    "storename": storename,
                    "bucket": bucket,
                    "edit": True,
                    "edit_detail": detail[1],
                    "policy_detail": policy_details,
                },
            )
    except ClientError:
        request.session["invalid"] = True
        return RedirectResponse(
            f"/object-store/{storename}/buckets/{bucket}/policy", status_code=303
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
