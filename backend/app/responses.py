import uuid
from typing import Any


def ok(data: Any) -> dict[str, Any]:
    return {"data": data, "requestId": str(uuid.uuid4())}
