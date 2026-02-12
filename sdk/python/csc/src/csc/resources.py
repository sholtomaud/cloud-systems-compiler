from typing import Optional, List, Any, Dict
from .registry import global_registry

class Resource:
    def __init__(self, name: str):
        self.name = name
        global_registry.register_resource(name, self)

class Table(Resource):
    def __init__(
        self,
        name: str,
        partition_key: str = "id",
        sort_key: Optional[str] = None,
        encryption: bool = True,
        backups: bool = True,
        ttl: Optional[str] = None,
        **kwargs
    ):
        super().__init__(name)
        self.partition_key = partition_key
        self.sort_key = sort_key
        self.encryption = encryption
        self.backups = backups
        self.ttl = ttl
        self.extra_config = kwargs
        self._data: Dict[Any, Any] = {}

    def get(self, id: Any) -> Optional[Any]:
        return self._data.get(id)

    def put(self, item: Any):
        # Assuming item has the partition key or is a dict
        if isinstance(item, dict):
            id_val = item.get(self.partition_key)
            if id_val is not None:
                self._data[id_val] = item
        else:
            # Fallback for simple values if appropriate, or objects with attributes
            id_val = getattr(item, self.partition_key, None)
            if id_val is not None:
                self._data[id_val] = item

    def scan(self) -> List[Any]:
        return list(self._data.values())

    def update(self, id: Any, data: Any):
        if id in self._data:
            if isinstance(self._data[id], dict) and isinstance(data, dict):
                self._data[id].update(data)
            else:
                self._data[id] = data

    def delete(self, id: Any):
        if id in self._data:
            del self._data[id]

class LogStream(Resource):
    def __init__(
        self,
        name: str,
        retention: str = "7d",
        encryption: bool = True,
        **kwargs
    ):
        super().__init__(name)
        self.retention = retention
        self.encryption = encryption
        self.extra_config = kwargs
        self._logs: List[Dict[str, Any]] = []

    def info(self, message: str, **kwargs):
        self._logs.append({"level": "INFO", "message": message, **kwargs})

    def audit(self, message: str, **kwargs):
        self._logs.append({"level": "AUDIT", "message": message, **kwargs})

    def write(self, entry: Any):
        self._logs.append({"level": "WRITE", "entry": entry})

class Cognito(Resource):
    def __init__(
        self,
        name: str,
        mfa: bool = False,
        password_policy: str = "strong",
        token_ttl: str = "1h",
        **kwargs
    ):
        super().__init__(name)
        self.mfa = mfa
        self.password_policy = password_policy
        self.token_ttl = token_ttl
        self.extra_config = kwargs
