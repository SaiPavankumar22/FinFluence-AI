"""Custom JSON response that safely serializes ObjectId / datetime returned from Mongo."""
import json
from datetime import datetime
from bson import ObjectId
from fastapi.responses import JSONResponse


class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class MongoJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(content, cls=MongoJSONEncoder).encode("utf-8")
