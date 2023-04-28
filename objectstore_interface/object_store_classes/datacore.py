import random
import string
from datetime import datetime
import requests as r
from requests.auth import HTTPBasicAuth
from fastapi import Request

from dateutil.relativedelta import relativedelta
from .base import ObjectStore

class DataCore(ObjectStore):

    def __init__(self, location: str, name: str = None, ) -> None:
        self.name = location.split(".")[0]
        self.location = location

    async def get_store(self, request: Request, password: str = None) -> dict:
        headers = {
            'Cookie': 'token=' + self.auth_access_key,
        }

        response = r.get(
            f"http://{self.location}:81/.TOKEN/?format=json",
            headers=headers
        )

        if response.status_code != 200:
              return self._return_error(response)
        
        access_keys = []
        expired_access_keys = []
        
        all_access_keys = response.json()

        for json_access_key in all_access_keys:
            access_key = {}
        # Update date fields to viewable format and check if they're expired/expiring.
            last_modified = datetime.strptime(json_access_key['last_modified'].split('T')[0], '%Y-%m-%d')
            lifepoint = datetime.strptime(json_access_key['lifepoint'].split(']')[0], '[%a, %d %b %Y %H:%M:%S %Z')
            expiring = True if lifepoint > datetime.today() and lifepoint < datetime.today() + relativedelta(weeks = 1) else False
            expired = True if lifepoint < datetime.today() else False

            access_key['last_modified'] = last_modified.strftime('%Y-%m-%d')
            access_key['lifepoint_date'] = lifepoint
            access_key['lifepoint'] = lifepoint.strftime('%Y-%m-%d')
            access_key['expiring'] = expiring
            access_key['expired'] = expired
            access_key['description'] = json_access_key['x_custom_meta_source']
            access_key['name'] = json_access_key['name']
            access_key['owner'] = json_access_key['x_owner_meta']

            if access_key['description'] != "JASMIN account auth access key":
                # Create a list of expired and active access keys.
                if not expired:
                    access_keys.append(access_key)
                else:
                    expired_access_keys.append(access_key)

        # If there are no active keys show the most recent expired key.
        if access_keys == [] and expired_access_keys != []:
            expired_access_keys.sort(key=lambda x: x['lifepoint_date'], reverse=True)
            access_keys.append(expired_access_keys[0])

        return {"status_code": response.status_code, "access_keys": access_keys}

    async def get_access_key(self, password, request: Request):
        response = r.get(f"http://{self.location}:81/.TOKEN/?format=json", auth=HTTPBasicAuth(request.session["token"]["userinfo"]["preferred_username"], password))
        if response.status_code != 200:
                return self._return_error(response)
        auth_access_keys = [ak for ak in response.json() if ak['x_custom_meta_source'] == "JASMIN account auth access key"]

        auth_access_key_name = False
        for auth_access_key in auth_access_keys:
                lifepoint = datetime.strptime(auth_access_key['lifepoint'].split(']')[0], '[%a, %d %b %Y %H:%M:%S %Z')
                if lifepoint > datetime.today():
                    auth_access_key_name = auth_access_key['name']

        # If no unexpired auth access key exists, create one.
        if not auth_access_key_name:
                expires = datetime.today() + relativedelta(weeks = 1)
                headers = {
                    'X-Custom-Meta-Source': 'JASMIN account auth access key',
                    'X-User-Token-Expires-Meta': expires.strftime('%Y-%m-%d'),
                }
                url = "http://" + self.location + ':81/.TOKEN/?format=json'
                response = r.post(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(request.session["token"]["userinfo"]["preferred_username"], password)
                )
                auth_access_key_name = response.text.split()[1]

                # Put the auth access key in the session. Add service id to name to make unique, 
                # as users could have multiple auth access keys (one for each of their services).
        self.auth_access_key = auth_access_key_name

        return {"status_code": 200, "access_key": auth_access_key_name, "error": None}
    
    async def delete_key(self, delete_access_key):
        url = f"http://{self.location}:81/.TOKEN/{delete_access_key}"
        headers = {
            'Cookie': 'token=' + self.auth_access_key,
        }
         
        response = r.delete(
            url,
            headers=headers,
        )

        if response.status_code != 200:
             return await self._return_error(response)
        
        return {"status_code": response.status_code, "error": None}
    
    async def create_key(self, description, expires):
        secret_key = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=64))
        headers = {
                'X-User-Secret-Key_meta': secret_key,
                'X-Custom-Meta-Source': description,
                'X-User-Token-Expires-Meta': expires,
                'Cookie': 'token=' + self.auth_access_key,
        }
        url = "http://" + self.location + ":81/.TOKEN/"

        response = r.post(
                url,
                headers=headers,
        )

        response_text = response.text

        if response.status_code != 201:
             return self._return_error(response)
        
        return {"status_code": response.status_code, "access_key": response_text.split()[1], "secret_key": secret_key}