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


@router.get("/object-store/{storename}/buckets/{bucket}/create")
async def permissions_page(request: Request, storename, bucket):
    """Displays the create permissions page.

    Also includes a list of templates to make it easier to add new ones. In future these could also have the variables needed for creation in them.
    """
    try:
        template_list = [
            {"name": "read-only-all", "readable_name": "Read-only access for Everyone"},
            {"name": "read-only-users", "readable_name": "Read-only access for Users"},
            {"name": "full-access-users", "readable_name": "Full access for Users"},
            {
                "name": "uploads-no-login",
                "readable_name": "Allow bucket uploads without login",
            },
            {
                "name": "no-uploads-no-login",
                "readable_name": "Prevent bucket uploads without login",
            },
            {
                "name": "bucket-manage-users",
                "readable_name": "Grant bucket management to Users",
            },
        ]
        invalid = request.session.pop("invalid", False)
        return templates.TemplateResponse(
            "bucket_pages/create.html",
            {
                "request": request,
                "view": "create",
                "storename": storename,
                "bucket": bucket,
                "edit_detail": "false",
                "templates": template_list,
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


@router.post("/object-store/{storename}/buckets/{bucket}/create")
async def create_permissions(
    request: Request,
    storename,
    bucket,
    actionArray: Annotated[str, Form()],
    application: Annotated[str, Form()],
    policyName: Annotated[str, Form()],
    direction: Annotated[str, Form()],
    edit: Annotated[str, Form()],
    userNames: Annotated[str, Form()] = None,
    groupNames: Annotated[str, Form()] = None,
):
    """Takes the response to the form and passes it to the create_policy function"""
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])
        response = await object_store.create_policy(
            actionArray,
            groupNames,
            userNames,
            application,
            policyName,
            direction,
            bucket,
            edit,
        )

        return RedirectResponse(
            f"/object-store/{storename}/buckets/{bucket}/policy", status_code=303
        )
    except ClientError:
        request.session["invalid"] = True
        return RedirectResponse(
            f"/object-store/{storename}/buckets/{bucket}/create", status_code=303
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


@router.post("/object-store/{storename}/buckets/{bucket}/templates")
async def template_permissions(
    request: Request,
    storename,
    bucket,
    template: Annotated[str, Form()],
    userNames: Annotated[str, Form()] = None,
    groupNames: Annotated[str, Form()] = None,
):
    """Takes the response to the form and passes the correct information to the create_policy function."""
    try:
        object_store: ObjectStore = storefromjson(request.session[storename])
        if template == "read-only-all":
            response = await object_store.create_policy(
                actions="GetObject",
                groups="null",
                users="null",
                application="Anonymous",
                bucket=bucket,
                name="Read-only access for Everyone",
                direction="Allow",
            )
        if template == "read-only-users":
            response = await object_store.create_policy(
                actions="GetObject",
                groups="null",
                users="null",
                application="All",
                bucket=bucket,
                name="Read-only access for Users",
                direction="Allow",
            )
        if template == "full-access-users":
            response = await object_store.create_policy(
                actions="*",
                groups="null",
                users="null",
                direction="Allow",
                application="All",
                bucket=bucket,
                name="Full access for Users",
            )
        if template == "uploads-no-login":
            response = await object_store.create_policy(
                actions="CopyObject,CreateObject,PutObject",
                groups="null",
                users="null",
                application="Anonymous",
                bucket=bucket,
                name="Allow bucket uploads without login",
                direction="Allow",
            )
        if template == "no-uploads-no-login":
            response = await object_store.create_policy(
                actions="*",
                groups="null",
                users="null",
                application="Anonymous",
                bucket=bucket,
                name="Prevent bucket uploads without login",
                direction="Deny",
            )
        if template == "bucket-manage-users":
            response = await object_store.create_policy(
                actions="CopyBucket,CreateBucket,DeleteBucket,GetBucket,ListBucket",
                groups="null",
                users="null",
                application="All",
                bucket=bucket,
                name="Grant bucket management to Users",
                direction="Allow",
            )
        if template == "bucket-group-access":
            response = await object_store.create_policy(
                actions="*",
                groups=groupNames,
                users=userNames,
                application="Users",
                bucket=bucket,
                name="Grant bucket management to Users",
                direction="Allow",
            )

        return RedirectResponse(
            f"/object-store/{storename}/buckets/{bucket}/policy", status_code=303
        )
    except ClientError:
        request.session["invalid"] = True
        return RedirectResponse(
            f"/object-store/{storename}/buckets/{bucket}/create", status_code=303
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
