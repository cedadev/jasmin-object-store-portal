import pytest
from fastapi.templating import Jinja2Templates
from starlette.config import Config
from objectstore_interface.main import app
from bs4 import BeautifulSoup
import tests.conftest
from fastapi.testclient import TestClient
from fastapi import Form
import json
from unittest.mock import Mock, patch, MagicMock
from objectstore_interface.object_store_classes.datacore import DataCore
import jsonpickle
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from requests import Response
import base64
import asyncio
from objectstore_interface.object_store_classes.datacore import DataCore

templates = Jinja2Templates(directory="objectstore_interface/templates")
with open("tests/test.json") as token_json:
    token_str = json.load(token_json)
token = {"options": {"token": token_str}}
#session = config("session")
client = TestClient(app)

#Mock the response from the datacore api
mock_response = MagicMock()
mock_response.status_code = 200
today = datetime.today()
today = today.replace(tzinfo=timezone.utc)
mock_response.json.return_value = [
    {
        'x_owner_meta': 'test', 
        'last_modified': '2023-04-12T14:39:45.500000Z', 
        'x_token_domain_meta': 'cedadev-o.s3.jc.rl.ac.uk', 
        'name': 'access-key-tested', 
        'lifepoint': f'[{(today + relativedelta(weeks=3)).strftime("%a, %d %b %Y %H:%M:%S %Z")}] reps=2, [] delete', 
        'x_custom_meta_source': 'JASMIN account auth access key'
    },
    {
        'x_owner_meta': 'test', 
        'last_modified': '2023-04-13T08:00:25.496000Z', 
        'x_token_domain_meta': 'cedadev-o.s3.jc.rl.ac.uk', 
        'name': 'test-expiry', 
        'lifepoint': f'[{(today + relativedelta(days=5)).strftime("%a, %d %b %Y %H:%M:%S %Z")}] reps=2, [] delete', 
        'x_custom_meta_source': 'test-expiry-key'
    }, 
    {
        'x_owner_meta': 'test', 
        'last_modified': '2023-04-03T08:22:17.728000Z', 
        'x_token_domain_meta': 'cedadev-o.s3.jc.rl.ac.uk', 
        'name': 'test-long-term', 
        'lifepoint': f'[{(today + relativedelta(weeks=3)).strftime("%a, %d %b %Y %H:%M:%S %Z")}] reps=2, [] delete', 
        'x_custom_meta_source': 'test-key'
    },
]

class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)

def test_read_main():
    response = client.get("/", headers={"token": json.dumps(token)})
    HTMLResponse = BeautifulSoup(response.text)
    assert HTMLResponse.p.string == "Here, you can manage you object store access keys."
    assert response.has_redirect_location == False


def test_read_jasmin_password_page():
    response = client.get("/object-store/cedadev-o", headers={"token": json.dumps(token)})

    HTMLResponse = BeautifulSoup(response.text)

    assert response.status_code == 200
    assert HTMLResponse.find("h3", string="Please confirm your Jasmin password") is not None

@patch('objectstore_interface.object_store_classes.datacore.r')
def test_jasmin_password_page(mock_get):
    test_datacore = DataCore("cedadev-o.s3.jc.rl.ac.uk")
    test_datacore.auth_access_key = "random"
    payload = {"password": "pass"}
    token["options"]["cedadev-o"] = jsonpickle.encode(test_datacore)
    mock_get.get.return_value = mock_response
    
    response = client.post("/object-store/cedadev-o", headers={"token": json.dumps(token)}, data=payload)

    session = base64.standard_b64decode(response.cookies["session"])

    assert response.status_code == 200
    assert json.loads(session)["access_key_cedadev-o"] == "access-key-tested"

@patch('objectstore_interface.pages.login_pages.login.oauth', new_callable=AsyncMock)
def test_read_store_list(mock_services):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"login_services": {"jasmin-login": ["USER"]}, "group_workspaces": {"cedaproc": ["USER"]}, "additional_services": {"ceda-developer": ["USER"]}, "object_store": {"cedadev-o": ["USER"]}}
    mock_services.accounts.get.return_value = mock_response
    
    response = client.get("/object-store", headers={"token": json.dumps(token)})

    HTMLResponse = BeautifulSoup(response.text)
    assert HTMLResponse.h3.string == "Object-Store: cedadev-o"

@patch('objectstore_interface.object_store_classes.datacore.r')
def test_read_access_keys(mock_get: MagicMock):
    test_datacore = DataCore("cedadev-o.s3.jc.rl.ac.uk")
    test_datacore.auth_access_key = "random"
    token["options"]["cedadev-o"] = jsonpickle.encode(test_datacore)
    token["options"]["access_key_cedadev-o"] = "random"
    mock_get.get.return_value = mock_response

    response = client.get("/object-store/cedadev-o/access-keys", headers={"token": json.dumps(token)})

    HTMLResponse = BeautifulSoup(response.text)

    assert response.status_code == 200
    assert HTMLResponse.table["class"] == ["table", "table-striped", "table-bordered"]
    assert HTMLResponse.find("a", string="View")["class"] == ["nav-link", "active"]
    assert HTMLResponse.find("td", string="test-expiry").find_parent("tr")["class"] == ["table-warning"]

def test_read_create_access_keys():
    response = client.get("/object-store/cedadev-o/create-keys", headers={"token": json.dumps(token)})
    HTMLResponse = BeautifulSoup(response.text)
    assert response.status_code == 200
    assert HTMLResponse.find("a", string="Create")["class"] == ["nav-link", "active"]

@patch('objectstore_interface.object_store_classes.datacore.r')
def test_create_access_keys(mock_post):
    today = datetime.today()
    payload = {"expires": f"{(today+relativedelta(weeks=2)).strftime('%d/%m/%Y')}", "description": "test-create-key"}
    print(payload)

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.text = "Token randomstring issued for test in cedadev-o.s3.jc.rl.ac.uk"
    mock_post.post.return_value = mock_response

    response = client.post("/object-store/cedadev-o/create-keys", headers={"token": json.dumps(token)}, data=payload)

    HTMLResponse = BeautifulSoup(response.text)

    assert HTMLResponse.find("code", string="randomstring") is not None
    assert response.status_code == 200


@pytest.mark.asyncio
@patch('objectstore_interface.object_store_classes.datacore.r')
async def test_delete_access_keys(mock_delete):
    mock_response - MagicMock()
    mock_response.status_code = 200
    mock_delete.delete.return_value = mock_response
    datacore = DataCore("cedadev-o.s3.jc.rl.ac.uk")
    datacore.auth_access_key = "random"
    
    response = await datacore.delete_key("test-long-term")

    assert response["status_code"] == 200