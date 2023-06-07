import json

class ObjectStore():
    def __init__(self, name, location) -> None:
        self.name = name
        self.location = location

    async def get_store(self) -> dict:
        """Get a specific object store
        
        Returns the access keys in a dictionary.
        """
        pass

    async def get_buckets(self):
        """Gets an s3 list of buckets"""
        pass
    
    async def get_bucket_details(self, bucket):
        """Gets the list of s3 policies in buckets"""
        pass
    
    async def get_access_key(self):
        """Gets or creates the access key used to authenticate with the store.
        This avoids the program needing to store the users password. Also creates
        an s3 key for use with buckets.
        """
        pass

    async def create_key(self):
        """Creates a key based on the Users parameters.
        These parameters will typically be provided via a 
        form post request.

        Arguments:
        description -- Name of the key
        expires -- When the key should expire
        """
        pass

    async def delete_key(self):
        """ Delete the key requested by the user.
        Simple delete request to the object store.
        """
        pass

    async def create_policy(self):
        """Creates a policy using the users selected options.

        The options will typically come from a form or prefilled templates.\n
        Arguments:\n
        actions -- List of actions that the policy will allow or deny,\n
        groups, users -- List of Users or groups to apply to,\n
        application -- Whether to apply to anonymous users, logged in users, or specific groups and users,\n
        name -- Name of policy,\n
        direction -- Whether he policy allows or denies the actions,\n
        bucket -- Which bucket the policy is in,\n
        edit = "false" -- Flag to tell the function to delete the existing policy so that it's not being duplicated.
        """
        pass

    async def delete_policy(self):
        """Deletes policy specified by user"""
        pass

    async def get_individual_policy(self):
        """Gets a policy by index number"""
        pass

    def _return_error(self, response):
        return {"status_code": response.status_code, "error": f"{response.status_code}: {response.text}"} 
    
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)