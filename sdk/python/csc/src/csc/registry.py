from typing import Dict, List, Any, Optional

class Registry:
    def __init__(self):
        self.app: Optional[Any] = None
        self.resources: Dict[str, Any] = {}
        self.routes: List[Dict[str, Any]] = []
        self.middlewares: List[Any] = []

    def register_app(self, app):
        self.app = app

    def register_resource(self, name: str, resource):
        self.resources[name] = resource

    def register_route(self, route_info: Dict[str, Any]):
        self.routes.append(route_info)

    def register_middleware(self, middleware):
        self.middlewares.append(middleware)

    def clear(self):
        self.app = None
        self.resources = {}
        self.routes = []
        self.middlewares = []

global_registry = Registry()
