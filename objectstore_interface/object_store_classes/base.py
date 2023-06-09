

class ObjectStore():
    def __init__(self, name, location) -> None:
        self.name = name
        self.location = location

    async def get_store(self) -> dict:
        pass

    async def get_access_key(self):
        pass

    async def create_key(self):
        pass

    async def delete_key(self):
        pass

    async def _return_error(self, response):
          return {"status_code": response.status_code, "error": f"{response.status_code}: {response.content.strip()}"} 