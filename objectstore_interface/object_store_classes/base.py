import json

class ObjectStore():
    def __init__(self, name, location) -> None:
        self.name = name
        self.location = location

    async def get_store(self) -> dict:
        pass

    async def get_buckets(self):
        pass
    
    async def get_bucket_details(self, bucket):
        pass
    
    async def get_access_key(self):
        pass

    async def create_key(self):
        pass

    async def delete_key(self):
        pass

    async def create_policy(self):
        pass

    async def delete_policy(self):
        pass

    async def get_individual_policy(self):
        pass

    def _return_error(self, response):
        return {"status_code": response.status_code, "error": f"{response.status_code}: {response.text}"} 
    
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)