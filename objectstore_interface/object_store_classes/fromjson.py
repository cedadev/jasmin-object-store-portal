import json, ast
from objectstore_interface.object_store_classes.datacore import DataCore
from objectstore_interface.object_store_classes.base import ObjectStore

def storefromjson(jstring):
    json_info: dict = json.loads(jstring)
    if json_info["type"] == "Datacore":
        objectstore = DataCore(location=json_info["location"])
        for k in json_info.keys():
            objectstore.__setattr__(k, json_info[k])
    return objectstore
            
