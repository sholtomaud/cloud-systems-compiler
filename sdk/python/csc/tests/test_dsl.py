import pytest
from csc import App, Table, LogStream, route, auth, global_registry

@pytest.fixture(autouse=True)
def clear_registry():
    global_registry.clear()
    yield

def test_app_declaration():
    app = App(name="test-api", region="us-west-2")
    assert global_registry.app == app
    assert global_registry.app.name == "test-api"
    assert global_registry.app.region == "us-west-2"

def test_table_declaration():
    users = Table(name="users", partition_key="user_id")
    assert "users" in global_registry.resources
    assert global_registry.resources["users"] == users
    assert users.partition_key == "user_id"

def test_logstream_declaration():
    logs = LogStream(name="app-logs", retention="30d")
    assert "app-logs" in global_registry.resources
    assert logs.retention == "30d"

def test_route_and_auth_decorators():
    @auth(cognito=True, scopes=["read"])
    @route("/data", method="GET")
    def get_data():
        return {"data": "ok"}

    assert len(global_registry.routes) == 1
    route_info = global_registry.routes[0]
    assert route_info["path"] == "/data"
    assert route_info["methods"] == ["GET"]
    assert route_info["auth"]["cognito"] is True
    assert route_info["auth"]["scopes"] == ["read"]
    assert route_info["handler"] == get_data

def test_table_functional():
    table = Table(name="test-table", partition_key="pk")
    table.put({"pk": "1", "name": "Alice"})
    assert table.get("1") == {"pk": "1", "name": "Alice"}

    table.update("1", {"name": "Bob"})
    assert table.get("1")["name"] == "Bob"

    assert len(table.scan()) == 1
    table.delete("1")
    assert table.get("1") is None

def test_logstream_functional():
    logs = LogStream(name="test-logs")
    logs.info("test message", user="admin")
    logs.audit("sensitive action")

    assert len(logs._logs) == 2
    assert logs._logs[0]["level"] == "INFO"
    assert logs._logs[0]["user"] == "admin"
    assert logs._logs[1]["level"] == "AUDIT"
