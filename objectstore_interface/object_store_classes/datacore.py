import random
import yaml, json
import ast
import boto3
import string
from datetime import datetime
import requests as r
from requests.auth import HTTPBasicAuth
from fastapi import Request
from botocore.exceptions import ClientError

from dateutil.relativedelta import relativedelta
from .base import ObjectStore

class DataCore(ObjectStore):

    def __init__(self, location: str, name: str = None, ) -> None:
        self.name = location.split(".")[0]
        self.location = location
        self.type = "Datacore"

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

            if access_key['description'] != "JASMIN account auth access key" and access_key['description'] != 'JASMIN account auth access key S3':
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
        with open("conf/common.secrets.yaml") as confile:
            config = yaml.safe_load(confile)
        response = r.get(f"http://{self.location}:81/.TOKEN/?format=json", auth=HTTPBasicAuth(request.session["token"]["userinfo"]["preferred_username"], password))
        if response.status_code != 200:
                return self._return_error(response)
        auth_access_keys = [ak for ak in response.json() if ak['x_custom_meta_source'] == "JASMIN account auth access key"]
        s3_auth_access_keys = [ak for ak in response.json() if ak['x_custom_meta_source'] == "JASMIN account auth access key S3"]

        auth_access_key_name = False
        for auth_access_key in auth_access_keys:
                lifepoint = datetime.strptime(auth_access_key['lifepoint'].split(']')[0], '[%a, %d %b %Y %H:%M:%S %Z')
                if lifepoint > datetime.today():
                    auth_access_key_name = auth_access_key['name']

        s3_auth_access_key_name = False
        for s3_auth_access_key in s3_auth_access_keys:
                lifepoint = datetime.strptime(s3_auth_access_key['lifepoint'].split(']')[0], '[%a, %d %b %Y %H:%M:%S %Z')
                if lifepoint > datetime.today():
                    s3_auth_access_key_name = s3_auth_access_key['name']

        # If no unexpired auth access key exists, create one.
        
        if not auth_access_key_name or not s3_auth_access_key_name:
                expires = datetime.today() + relativedelta(weeks = 1)
                secret_key = config["s3"]["auth_secret"]

                #create standard key for general use
                headers = {
                    'X-Custom-Meta-Source': 'JASMIN account auth access key',
                    'X-User-Token-Expires-Meta': expires.strftime('%Y-%m-%d'),
                }
                url = "http://" + self.location + ':81/.TOKEN/'
                response = r.post(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(request.session["token"]["userinfo"]["preferred_username"], password)
                )
                auth_access_key_name = response.text.split()[1]

                # Create s3 key for object store
                headersS3 = {
                    'X-User-Secret-Key-Meta': secret_key,
                    'X-Custom-Meta-Source': 'JASMIN account auth access key S3',
                    'X-User-Token-Expires-Meta': expires.strftime('%Y-%m-%d'),
                    'Cookie': 'token=' + auth_access_key_name
                }
                responseS3 = r.post(
                    url,
                    headers=headersS3,
                )

                s3_auth_access_key_name = responseS3.text.split()[1]

                # Put the auth access key in the session. Add service id to name to make unique, 
                # as users could have multiple auth access keys (one for each of their services).
        self.auth_access_key = auth_access_key_name
        self.s3_auth_access_key = s3_auth_access_key_name

        return {"status_code": 200, "access_key": auth_access_key_name, "s3_access_key": s3_auth_access_key_name, "error": None}
    
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
             return self._return_error(response)
        
        return {"status_code": response.status_code, "error": None}
    
    async def create_key(self, description, expires):
        secret_key = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=64))
        headers = {
                'X-User-Secret-Key-Meta': secret_key,
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
    
    async def _init_bucket_resource(self, bucket):
        with open("conf/common.secrets.yaml") as confile:
            config = yaml.safe_load(confile)
        
        url = "http://" + self.location
        
        jasmin_session = boto3.Session()
        jasmin_s3 = jasmin_session.resource(
            "s3", 
            endpoint_url=url, 
            aws_access_key_id= self.s3_auth_access_key,
            aws_secret_access_key= config["s3"]["auth_secret"]
        )
        jasmin_bucket = jasmin_s3.Bucket(bucket)

        return jasmin_bucket
    
    async def get_buckets(self):
        with open("conf/common.secrets.yaml") as confile:
            config = yaml.safe_load(confile)
        url = "http://" + self.location
        jasmin_session = boto3.Session()
        
        jasmin_s3 = jasmin_session.client(
            "s3", 
            endpoint_url=url, 
            aws_access_key_id= self.s3_auth_access_key,
            aws_secret_access_key= config["s3"]["auth_secret"]
        )
        response = jasmin_s3.list_buckets()
        return response["Buckets"]
        
    async def get_bucket_details(self, bucket):
        jasmin_bucket = await self._init_bucket_resource(bucket)
        try:
            response = jasmin_bucket.Policy().policy
        except Exception as e:
             return {"hasPolicy": False, "policy": []}
        response_dict = ast.literal_eval(response)
        return {"hasPolicy": True, "policy": response_dict["Statement"]}
    
    async def create_policy(self, actions, groups, users, application, name, direction, bucket, edit = "false"):
        with open("conf/common.secrets.yaml") as confile:
            config = yaml.safe_load(confile)
        url = "http://" + self.location
        jasmin_bucket = await self._init_bucket_resource(bucket)
        jasmin_client = boto3.client(
            "s3", 
            endpoint_url=url, 
            aws_access_key_id= self.s3_auth_access_key,
            aws_secret_access_key= config["s3"]["auth_secret"]
        )
        print(actions)
        if application != "Users":
            groups = None
            users = None

        try:
            bucket_policy_raw = jasmin_bucket.Policy().policy
        except ClientError:
            bucket_policy_raw = f'{{"Version":"2008-10-17","Id":"{bucket} policy","Statement":[]}}'

        bucket_policy = ast.literal_eval(bucket_policy_raw)
        
        if edit != "false":
             edit_num = ast.literal_eval(edit)

             del bucket_policy["Statement"][edit_num]

        actionList = actions.split(',')
        fullList = ['ListBucket', 'GetBucket', 'DeleteBucket', 'CopyBucket', 'GetBucketAcl', 'PutBucketAcl', 'GetBucketCORS', 'PutBucketCORS', 'GetBucketObjectLocking', 'PutBucketObjectLocking', 'GetObject', 'PutObject', 'DeleteObject', 'CreateObject', 'CopyObject', 'AppendObject', 'GetObjectAcl', 'PutObjectAcl', 'GetObjectRetention', 'PutObjectRetention', 'PutObjectLegalHold', 'BypassGovernanceRetention']
             
        policyArray = {
            "Sid": name,
            "Effect": direction,
            "Principal":{},
            "Action": [],
            "Resource": "*"
        }
        policyArray["Action"] = ["*"] if all(item in actionList for item in fullList) else actionList

        if groups == None and users == None:
            policyArray["Principal"] = {"user":["*"]} if application == "All" else {"anonymous":["*"]}
        else:
            groupList = groups.split(",") if groups != None else []
            userList = users.split(",") if users != None else []

            policyArray["Principal"] = {
                "user": userList,
                "group": groupList
            }
        bucket_policy["Statement"].append(policyArray)

        bucket_policy_str = json.dumps(bucket_policy)
        
        jasmin_client.put_bucket_policy(Bucket=bucket, Policy=bucket_policy_str)

        return {"status_code": 200}
    
    async def delete_policy(self, bucket, policy):
        with open("conf/common.secrets.yaml") as confile:
            config = yaml.safe_load(confile)
        url = "http://" + self.location
        jasmin_bucket = await self._init_bucket_resource(bucket)
        jasmin_client = boto3.client(
            "s3", 
            endpoint_url=url, 
            aws_access_key_id= self.s3_auth_access_key,
            aws_secret_access_key= config["s3"]["auth_secret"]
        )

        bucket_policy_raw = jasmin_bucket.Policy().policy
        bucket_policy = ast.literal_eval(bucket_policy_raw)
        policy_num = ast.literal_eval(policy)

        del bucket_policy["Statement"][policy_num]

        bucket_policy_str = json.dumps(bucket_policy)
        jasmin_client.put_bucket_policy(Bucket=bucket, Policy=bucket_policy_str)

        return {"status_code": 200}
    
    async def get_individual_policy(self, bucket, pol_number):
        jasmin_bucket = await self._init_bucket_resource(bucket)

        bucket_policy_raw = jasmin_bucket.Policy().policy
        bucket_policy = ast.literal_eval(bucket_policy_raw)
        policy_num = ast.literal_eval(pol_number)

        return bucket_policy["Statement"][policy_num]