from typing import List, Optional, Callable, Any, Dict, Union
from .registry import global_registry

class App:
    def __init__(
        self,
        name: str,
        stage: str = "dev",
        region: str = "us-east-1",
        **kwargs
    ):
        self.name = name
        self.stage = stage
        self.region = region
        self.config = kwargs
        global_registry.register_app(self)

def _get_or_create_metadata(func: Callable) -> Dict[str, Any]:
    if not hasattr(func, "_csc_metadata"):
        func._csc_metadata = {}
    return func._csc_metadata

def route(
    path: str,
    method: Optional[str] = None,
    methods: Optional[List[str]] = None,
    public: bool = False
):
    if methods is None:
        if method:
            methods = [method]
        else:
            methods = ["GET"]

    def decorator(func: Callable):
        metadata = _get_or_create_metadata(func)
        metadata.update({
            "path": path,
            "methods": methods,
            "public": public
        })

        # Check if already registered to avoid duplicates or update info
        existing = next((r for r in global_registry.routes if r["handler"] == func), None)
        if existing:
            existing.update({
                "path": path,
                "methods": methods,
                "public": public
            })
        else:
            global_registry.register_route({
                "handler": func,
                "path": path,
                "methods": methods,
                "public": public,
                "auth": metadata.get("auth")
            })
        return func
    return decorator

def auth(
    resource: Optional[Any] = None,
    cognito: Optional[bool] = None,
    scopes: Optional[List[str]] = None
):
    if scopes is None:
        scopes = []

    def decorator(func: Callable):
        metadata = _get_or_create_metadata(func)
        auth_info = {
            "resource": resource,
            "cognito": cognito,
            "scopes": scopes
        }
        metadata["auth"] = auth_info

        # Update existing route registration
        existing = next((r for r in global_registry.routes if r["handler"] == func), None)
        if existing:
            existing["auth"] = auth_info

        return func
    return decorator

def middleware(func: Callable):
    global_registry.register_middleware(func)
    return func
