import json, ast
from objectstore_interface.object_store_classes.datacore import DataCore
from objectstore_interface.object_store_classes.base import ObjectStore


def storefromjson(jstring):
    """Creates store from json string using the type to decide which store to create."""
    json_info: dict = json.loads(jstring)
    if json_info["type"] == "Datacore":
        objectstore = DataCore(location=json_info["location"])
    else:
        # Handle base ObjectStore or unknown types
        objectstore = ObjectStore(
            name=json_info.get("name"), location=json_info["location"]
        )

    # Set all attributes from the JSON
    for k in json_info.keys():
        objectstore.__setattr__(k, json_info[k])

    return objectstore
