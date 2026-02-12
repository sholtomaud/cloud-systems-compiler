# CSC Python SDK

The Python SDK for the Cloud Systems Compiler (CSC). It allows you to define cloud-native APIs using a FastAPI-like syntax.

## Installation

```bash
pip install csc
```

## Usage

```python
from csc import App, Table, LogStream, route, auth

app = App(
    name="user-api",
    region="us-east-1"
)

users = Table(
    name="users",
    partition_key="id"
)

logs = LogStream(name="app-logs")

@auth(cognito=True, scopes=["user:read"])
@route("/users/{id}", method="GET")
def get_user(id: str):
    logs.info(f"Fetching user {id}")
    return users.get(id)

@route("/health")
def health():
    return {"status": "ok"}
```

## Core Components

- `App`: Main application declaration.
- `Table`: DynamoDB table abstraction.
- `LogStream`: CloudWatch Logs abstraction.
- `@route`: Decorator for defining API endpoints.
- `@auth`: Decorator for adding authentication (Cognito) to routes.
