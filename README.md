# Cloud System Compiler (CSC) Specification

## Overview

A compiler toolchain that transforms high-level API definitions (written in Python with FastAPI-like syntax plus cloud resource declarations) into cloud-native infrastructure, specifically targeting AWS API Gateway + VTL (with minimal Lambda usage) while preserving full local development and testing capabilities.

## Core Problem Statement

FastAPI provides excellent developer experience (auto-generated OpenAPI, type validation, local testing) but is not AWS cloud-native. Deploying FastAPI to AWS requires either:
- Fat Lambda (monolithic, slow cold starts)
- Containers on ECS/EKS (loses serverless economics)
- Many Lambdas behind API Gateway (loses FastAPI ergonomics)

**Goal**: Achieve both FastAPI-level developer experience AND AWS-native infrastructure benefits.

## Architectural Principle

**Python + FastAPI-like syntax as authoring language, compiler generates cloud-native infrastructure**

Developers write in familiar Python with FastAPI-like decorators, but add cloud resource declarations. The compiler transforms this into optimized cloud infrastructure.

```python
# Developer writes familiar Python/FastAPI syntax
from csc import *

user_db = DynamoDB(name="users")  # Cloud resource with sensible defaults

@route("/users/{id}")
@auth(cognito, scopes=["user:read"])
def get_user(id: str) -> User:
    return user_db.get(id)
```

This compiles to:
- OpenAPI schema
- API Gateway + VTL (maximum VTL usage, minimal Lambda)
- IAM policies (AWS-native Cognito integration, NOT JWT Lambda authorizers)
- DynamoDB tables with encryption, PITR, autoscaling (by default)
- Full local testing environment

**Key insight**: Use Python/FastAPI as the source language, not the runtime.

## Compiler Pipeline Architecture

### Layer 1: Source Language (High-Level API Definition)
```python
@route("/users/{id}")
@auth(cognito, scopes=["user:read"])
def get_user(id: int) -> User:
    return dynamodb("users").get(id)
```

### Layer 2: Semantic IR (Platform-Agnostic)
- OpenAPI schema
- Auth requirements
- Rate limits
- CORS policies
- Quotas
- Workflows
- Integrations
- Security policies

### Layer 3: Cloud IR (Platform-Specific Mapping)

**For AWS:**
- API Gateway resources
- Method integrations
- VTL templates
- IAM roles & policies
- Cognito pools
- WAF rules
- Usage plans

**For Azure:**
- API Management
- Functions
- AAD auth
- WAF policies

**For GCP:**
- API Gateway/ESPv2
- Cloud Functions
- IAM
- Cloud Armor

### Layer 4: Execution IR (Deployment Artifacts)

**Execution IR (Intermediate Representation)** is the final compiled output that can be deployed to cloud infrastructure. Unlike source code or semantic models, this is the actual deployment specification.

**Primary target: CloudFormation / CDK Cloud Assembly**
- Direct AWS CloudFormation templates
- CDK Cloud Assembly (JSON manifests + dependency graphs)
- No paid runtime dependencies (no Terraform Cloud, no external services)
- Can optionally support OpenTofu for multi-cloud scenarios

**Why not Terraform as primary?**
- Terraform Cloud is now a paid service
- Adds external runtime dependency
- CloudFormation is native AWS, zero additional cost
- CDK Assembly provides clean IR with dependency resolution

**For multi-cloud (future):**
- OpenTofu (open-source Terraform fork)
- Direct ARM/Bicep generation (Azure)
- GCP Deployment Manager

### Deployment Workflow Details

**Compilation process:**
```bash
$ csc compile api.py
```

Compiler performs:
1. Parse Python AST
2. Validate types and semantics
3. Infer IAM policies (least privilege)
4. Generate OpenAPI schema
5. Decide VTL vs Lambda for each route
6. Generate VTL templates (where possible)
7. Generate Lambda code (where necessary)
8. Generate CloudFormation templates
9. Bundle assets (Lambda zips, VTL files)
10. Create deployment artifact

**Output structure:**
```
.csc-out/
├── openapi.yaml              # Generated OpenAPI spec
├── cloudformation/
│   ├── api-stack.yaml        # API Gateway resources
│   ├── auth-stack.yaml       # Cognito resources
│   ├── data-stack.yaml       # DynamoDB resources
│   └── iam-stack.yaml        # IAM roles & policies
├── vtl/
│   ├── get-user.vtl          # Request templates
│   └── get-user-response.vtl # Response templates
└── lambda/
    └── send-welcome/         # Only if complex logic needed which is not possible with VTL
        ├── handler.py
        └── requirements.txt
```

**Deployment execution:**
```bash
$ csc deploy --stage prod --region us-east-1
```

CSC orchestrates:
1. Package Lambda functions (if any)
2. Upload assets to S3
3. Create/update CloudFormation stacks (correct order)
4. Wait for stack completion
5. Run smoke tests
6. Output API URLs and endpoints

**Zero-downtime deployment:**
- Blue/green deployment for API Gateway
- Canary releases (10% → 50% → 100%)
- Automatic rollback on errors
- Health check validation

### AWS-Native Authentication: Cognito + IAM (No JWT Lambda Authorizers)

**Critical: Use AWS-native Cognito authorizers, NOT custom JWT Lambda authorizers**

**Why AWS-native integration is superior:**

**AWS-native Cognito Authorizer:**
- ✅ Zero Lambda invocations (auth happens at API Gateway layer)
- ✅ Zero cold start latency
- ✅ Zero custom code to maintain
- ✅ Native IAM integration
- ✅ Built-in token validation
- ✅ Automatic token caching
- ✅ No additional permissions required
- ✅ Free (no Lambda costs)
- ✅ Works with VTL seamlessly

**JWT Lambda Authorizer (❌ AVOID):**
- ❌ Requires Lambda invocation per request
- ❌ Cold start latency on auth
- ❌ Additional Lambda costs
- ❌ Custom validation code to maintain
- ❌ Additional IAM permissions complexity
- ❌ Caching requires manual configuration
- ❌ Another failure point

**Architecture Comparison:**

❌ **Wrong: JWT Lambda Authorizer**
```
Client → API Gateway → Lambda Authorizer → Validate JWT → Lambda Handler → DynamoDB
         (50ms)       (10-100ms cold)                     (10-100ms cold)
```

✅ **Correct: Native Cognito Authorizer**
```
Client → API Gateway (Cognito authorizer) → VTL → DynamoDB
         (5ms native validation)             (2ms)
```

**How the compiler generates this:**

```python
users = Cognito(name="users")

@route("/users/{id}")
@auth(users, scopes=["user:read"])
def get_user(id: str) -> User:
    return user_db.get(id)
```

**Compiler generates (CloudFormation):**
```yaml
# Cognito User Pool
UserPool:
  Type: AWS::Cognito::UserPool
  Properties:
    UserPoolName: users
    MfaConfiguration: OPTIONAL

# API Gateway Cognito Authorizer (NOT Lambda!)
CognitoAuthorizer:
  Type: AWS::ApiGateway::Authorizer
  Properties:
    Type: COGNITO_USER_POOLS
    IdentitySource: method.request.header.Authorization
    ProviderARNs:
      - !GetAtt UserPool.Arn

# API Gateway Method (uses native authorizer)
GetUserMethod:
  Type: AWS::ApiGateway::Method
  Properties:
    AuthorizationType: COGNITO_USER_POOLS  # ← AWS-native!
    AuthorizerId: !Ref CognitoAuthorizer
    AuthorizationScopes:
      - user:read
```

**Auth context propagation to VTL/Lambda:**

The Cognito authorizer injects auth context into the request:

```vtl
## VTL can access Cognito claims directly
#set($userId = $context.authorizer.claims.sub)
#set($userEmail = $context.authorizer.claims.email)
#set($scopes = $context.authorizer.claims.scope)

{
  "TableName": "users",
  "Key": {
    "id": {"S": "$userId"}
  }
}
```

**Benefits for developers:**
- No auth code to write
- No JWT libraries to manage
- No token validation logic
- No caching strategy needed
- Automatic security updates (AWS maintains it)
- Built-in rate limiting
- Built-in DDoS protection

**This is maximum cloud-native.** Zero custom auth code, zero Lambdas for auth.

### VTL vs Lambda: Maximizing VTL Usage

**Goal: Maximum VTL, Minimum Lambda**

VTL (Velocity Template Language) is native to API Gateway and should be preferred whenever possible.

**VTL (Preferred):**
- ✅ Zero cold starts (native to API Gateway)
- ✅ Zero additional cost (no Lambda invocation charges)
- ✅ Lower latency (~1-5ms)
- ✅ No permission chaining required
- ✅ Direct AWS service integration
- ✅ Perfect for CRUD operations
- ❌ Limited to request/response transformation
- ❌ No complex business logic
- ❌ Poor debugging experience (compiler handles this)

**Lambda (Only When Necessary):**
- ✅ Full programming capability
- ✅ Complex business logic
- ✅ External API calls
- ✅ Multi-step workflows
- ❌ Cold start latency (1-10ms for small functions)
- ❌ Additional IAM complexity
- ❌ Additional cost (per invocation + duration)

**Compiler Strategy: Automatically Choose VTL When Possible**

The compiler analyzes each route and automatically generates VTL when the operation is:
- Simple CRUD (Create, Read, Update, Delete)
- Direct DynamoDB query/scan/put/update
- Direct S3 get/put
- Simple request transformation
- Simple response mapping

**Example: Auto-VTL generation**
```python
@route("/users/{id}")
@auth(cognito)
def get_user(id: str) -> User:
    return user_db.get(id)
```

Compiler generates **VTL only** (no Lambda):
```vtl
## Request template
{
  "TableName": "users",
  "Key": {
    "id": {"S": "$input.params('id')"}
  }
}

## Response template
#set($item = $input.path('$.Item'))
{
  "id": "$item.id.S",
  "name": "$item.name.S",
  "email": "$item.email.S"
}
```

**Example: Requires Lambda**
```python
@route("/users/{id}/send-welcome-email")
@auth(cognito)
async def send_welcome(id: str) -> Status:
    user = user_db.get(id)
    await ses.send_email(user.email, template="welcome")
    await analytics.track("welcome_sent", user.id)
    return {"status": "sent"}
```

Compiler recognizes:
- Multiple external service calls (SES, analytics)
- Async operations
- Complex orchestration

Generates **Lambda** with minimal IAM permissions.

**Optimal Architecture: VTL + Lambda Layering**
```
Client 
  → API Gateway 
    → VTL (validation, auth context injection, simple routing)
      → Lambda (only for complex business logic)
        → AWS Services (DynamoDB, S3, SES, etc.)
```

**Statistics goal:**
- 80% of routes: VTL only
- 15% of routes: VTL + lightweight Lambda
- 5% of routes: Complex Lambda workflows

This achieves:
- Lowest possible latency
- Lowest possible cost  
- Maximum cloud-native integration
- Minimal IAM complexity

### Why Not Winglang?

Winglang failed because it tried to replace both application language AND infrastructure language simultaneously, violating separation of concerns:
- Created closed ecosystem
- Tried to hide irreducible cloud complexity
- Platform replacement vs. tooling improvement

**This compiler's approach:**
- Preserves existing execution models (HTTP, OpenAPI, IAM)
- Preserves existing security models
- Only replaces authoring layer (YAML/VTL/IAM JSON with better DSL)
- Compiler targeting existing platforms, not platform replacement

### Deployment Target

**Primary: Terraform IR**

Advantages:
- Cloud-agnostic (AWS, Azure, GCP, etc.)
- Mature dependency graph resolution
- State management
- Drift detection
- Huge provider ecosystem

Alternative for AWS-only: CDK Cloud Assembly

## Core Value Propositions

### 1. Local Development Equivalence
**Critical requirement**: What runs locally must behave identically to production.

The compiler must provide:
- Local API Gateway emulator
- Local Cognito emulator
- Local DynamoDB emulator
- Full auth flows
- Full request validation
- Full logging pipeline

This solves the biggest problem in serverless: loss of local executability.

### 2. Semantic L3 Constructs

Unlike CDK's structural L3 constructs, this compiler provides semantic L3:

**Compiler infers from intent:**
```python
@auth(cognito, scopes=["user:read"])
@route("/users/{id}")
def get_user(id: int) -> User:
    return dynamodb("users").get(id)
```

**Compiler generates:**
- Minimal IAM policies (least privilege)
- Cognito pool configuration
- JWT authorizer
- API Gateway method config
- Request validation schemas
- WAF rules
- Appropriate stack partitioning

### 3. Automatic Stack Management

Instead of manually managing separate stacks (auth, API, persistence, CI/CD), compiler automatically:
- Infers dependency graph
- Partitions for blast radius isolation
- Partitions for least privilege
- Partitions for deployment safety
- Generates optimal stack topology

### 4. Security by Construction

All permissions, trust relationships, and policies are:
- Derived from semantic intent
- Not hand-authored
- Enforced by compiler

Dramatically reduces:
- Over-permissioning
- Policy sprawl
- Human error
- Lateral movement risk

## Developer-First Design: Sensible Secure Defaults (PLOP Principle)

**PLOP = Principle of Least Privilege by Default**

The compiler assumes developers want:
- **Maximum security**
- **Minimum cost**
- **Zero configuration overhead**

### Default Behavior

All cloud resources have secure, cost-optimized defaults automatically applied:

**Simple declaration:**
```python
user_db = DynamoDB(name="users")
```

**Compiler automatically includes:**
- Encryption at rest (AWS KMS)
- Point-in-time recovery (PITR)
- Autoscaling (pay-per-request mode)
- Backup retention (7 days)
- DeletionProtection enabled
- Minimal IAM permissions (least privilege)

**Explicit configuration only when needed:**
```python
# Advanced users can override
user_db = DynamoDB(
    name="users",
    partition_key="userId",  # Change from default "id"
    sort_key="timestamp",     # Add sort key
    encryption=False,         # Disable encryption (not recommended)
    point_in_time_recovery=False,  # Reduce cost
    autoscale=False,          # Use provisioned capacity instead
    read_capacity=5,
    write_capacity=5
)
```

### Security Defaults for All Resources

**API Gateway:**
- WAF enabled (AWS Managed Rules)
- DDoS protection (Shield Standard, free tier)
- Rate limiting (100 req/sec default, 300 burst)
- CORS disabled by default (must explicitly enable)
- Request validation enabled
- CloudWatch logging enabled

**Cognito:**
- MFA encouraged (optional by default, can require)
- Strong password policy (min 8 chars, complexity requirements)
- Token TTL: 1 hour (access), 30 days (refresh)
- Email verification required
- Advanced security features enabled (compromised credentials detection)

**IAM:**
- Least privilege by default
- No wildcards in policies
- Explicit resource ARNs only
- Separate roles per function/route
- No cross-account access unless explicitly declared

**Lambda (when required):**
- Minimal memory (128MB default)
- Short timeout (3s default for API routes)
- No VPC access unless declared
- Environment variables encrypted
- X-Ray tracing enabled

### Cost Optimization Defaults

- DynamoDB: Pay-per-request (on-demand) mode
- API Gateway: REST API (cheaper than HTTP API for low volume)
- CloudWatch: 7-day retention (vs. infinite)
- S3: Intelligent-Tiering when storage declared
- Lambda: ARM64 Graviton2 processors (20% cheaper)

### The Developer Experience

**Beginner/tinkering developer:**
```python
# This is ALL you need for a secure, production-ready API
from csc import *

users = Cognito(name="users")
db = DynamoDB(name="users")

@route("/users/{id}")
@auth(users)
def get_user(id: str) -> User:
    return db.get(id)
```

Compiler generates:
- ✅ Encrypted database
- ✅ MFA-enabled auth
- ✅ WAF protection
- ✅ Rate limiting
- ✅ Audit logging
- ✅ Least-privilege IAM
- ✅ Request validation
- ✅ OpenAPI docs

**Advanced developer:**
```python
# Explicitly configure only what differs from defaults
db = DynamoDB(
    name="users",
    sort_key="created_at",  # Need composite key
    ttl_attribute="expires_at",  # Need TTL
    global_secondary_indexes=[  # Need GSI
        GSI(name="email-index", partition_key="email")
    ]
)
```

### Simple Example (Minimal Configuration)

```python
from csc import *

# Declare cloud resources with defaults
auth = Cognito(name="myapp-users")
db = DynamoDB(name="todos")

# Define routes
@route("/todos", methods=["GET"])
@auth(auth)
def list_todos() -> list[Todo]:
    return db.scan()

@route("/todos", methods=["POST"])
@auth(auth)
def create_todo(todo: NewTodo) -> Todo:
    return db.put(todo)

@route("/health", public=True)
def health():
    return {"status": "ok"}
```

That's it. Run `csc dev` for local testing, `csc deploy` for production.

### Full Example (Advanced Configuration)

```python
from csc import *

# Application config
app = Application(
    name="user-service",
    stage="prod",
    region="ap-southeast-2",
    logging=Logging(
        level="INFO",
        audit=True,
        retention_days=90  # Override default 7 days
    ),
    security=Security(
        ddos_protection=True,
        waf=True,
        rate_limits={
            "default": "100rps",
            "burst": "300rps"
        }
    )
)

# Identity with custom config
users = Cognito(
    name="users",
    mfa=True,  # Require MFA (default is optional)
    password_policy="strong",
    token_ttl="1h"
)

# Persistence with custom indexes
user_db = DynamoDB(
    name="users",
    partition_key="id",
    global_secondary_indexes=[
        GSI(name="email-index", partition_key="email", projection="ALL")
    ]
)

# Audit log with extended retention
audit_log = LogStore(
    name="audit",
    retention_days=365,  # Compliance requirement
    immutable=True
)

# Custom middleware
@middleware
def audit(ctx):
    audit_log.write({
        "user": ctx.identity.sub,
        "route": ctx.route,
        "timestamp": ctx.timestamp,
        "status": ctx.response.status
    })

# Routes
@route("/users/{id}", methods=["GET"])
@auth(users, scopes=["user:read"])
@audit
def get_user(id: str) -> User:
    return user_db.get(id)

@route("/users/{id}", methods=["PUT"])
@auth(users, scopes=["user:update"])
@audit
def update_user(id: str, user: UserUpdate) -> User:
    return user_db.update(id, user)
```

### Compiler Inference from Above

From this single semantic program, compiler generates:

**Identity:**
- Cognito User Pool
- OAuth scopes
- **AWS-native Cognito authorizer (NOT JWT Lambda authorizer)**
- Token TTL
- MFA enforcement
- IAM role trust chains with direct Cognito integration

**API Gateway:**
- Routes & methods
- OpenAPI schema
- Request/response validation
- Rate limits & throttling
- WAF integration
- CORS policies
- Usage plans

**IAM:**
- Per-route least privilege roles
- Cognito → API Gateway trust
- API Gateway → DynamoDB trust
- Log write permissions

**Persistence:**
- Encrypted DynamoDB tables
- Autoscaling policies
- Point-in-time recovery
- TTL policies

**Observability:**
- CloudWatch structured logs
- Immutable audit trail
- Retention policies

**Security:**
- WAF rules
- Shield Advanced integration
- Bot filtering
- Abuse protection

**CI/CD:**
- Immutable deployment pipeline
- Canary deploys
- Zero-downtime rollout
- Rollback strategy

## Execution Model

### Local Development
```bash
csc dev
```

Starts local emulation environment that behaves identically to production:
- Rust-based HTTP server with WASM runtime
- Emulated Cognito, DynamoDB, IAM
- Hot reload on source changes
- Structured logging to console

```bash
curl localhost:8080/todos
# Behaves exactly like production API Gateway
```

### Deployment
```bash
csc deploy --stage prod
```

Compiles to CloudFormation/CDK and deploys to AWS:
- Generates VTL templates (maximal usage)
- Generates IAM policies (minimal permissions)
- Generates API Gateway configuration
- Creates/updates CloudFormation stack
- Zero-downtime deployment with canary strategy

## WASM Compilation Pipeline & Local Runtime

### The Complete Flow: Python → WASM → Local Testing → AWS Deployment

```
┌─────────────────────────────────────────────────────────────┐
│ Developer writes Python with FastAPI-like syntax            │
│ + cloud resource declarations                               │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ CSC Compiler (written in Rust)                              │
│ - Parses Python AST                                          │
│ - Validates types & semantics                                │
│ - Infers IAM policies & security model                       │
│ - Generates OpenAPI schema                                   │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ├──────────────┬────────────────────────────┐
                  ▼              ▼                            ▼
         ┌────────────────┐  ┌──────────────┐    ┌────────────────────┐
         │ WASM Module    │  │ OpenAPI      │    │ CloudFormation/CDK │
         │ (for local dev)│  │ Schema       │    │ Templates          │
         └────────┬───────┘  └──────────────┘    └────────────────────┘
                  │
                  ▼
         ┌────────────────────────────────────────┐
         │ Local APIGW Runtime (Rust-based)       │
         │ - Executes WASM in sandboxed env       │
         │ - Emulates API Gateway behavior        │
         │ - Emulates Cognito auth flows          │
         │ - Emulates DynamoDB operations         │
         │ - Validates requests against OpenAPI   │
         │ - Enforces IAM policies locally        │
         └────────────────────────────────────────┘
                  │
                  ▼
         ┌────────────────────────────────────────┐
         │ localhost:8080                         │
         │ Behaves IDENTICALLY to production      │
         │ - Same auth flows                      │
         │ - Same validation                      │
         │ - Same routing                         │
         │ - Same error responses                 │
         └────────────────────────────────────────┘
```

### Why Rust → WASM?

**Rust for the compiler:**
- Type safety guarantees correctness
- Zero-cost abstractions for performance
- Excellent tooling (cargo, rustc)
- Can compile to native binary (single executable)
- Strong ecosystem for parsers (syn, pest)

**WASM for local runtime:**
- **Deterministic execution**: Same behavior every time
- **Sandboxing**: Secure isolation of API logic
- **Fast startup**: No cold start issues like Lambda
- **Portable**: Runs identically on Mac/Linux/Windows
- **Small binary size**: Efficient distribution
- **Language agnostic**: Could support Python/TS/Go sources in future

### Local Runtime Architecture (Rust-based)

The local runtime is a Rust application that:

1. **Loads WASM modules**: Compiled API logic runs in WASM sandbox
2. **HTTP server**: Listens on localhost (e.g., port 8080)
3. **Request handling**:
   - Parses incoming HTTP requests
   - Validates against OpenAPI schema
   - Executes authentication (emulated Cognito)
   - Routes to appropriate WASM function
   - Validates response
   - Returns HTTP response

4. **State emulation**:
   - In-memory DynamoDB (or embedded SQLite for persistence)
   - In-memory Cognito user pool
   - In-memory IAM policy engine

5. **Observability**:
   - Structured logging (same format as CloudWatch)
   - Request tracing
   - Performance metrics

### Example: What Gets Compiled

**Source (Python):**
```python
@route("/users/{id}")
@auth(cognito, scopes=["user:read"])
def get_user(id: str) -> User:
    return user_db.get(id)
```

**Compiles to:**

1. **WASM function** (for local dev):
   ```wat
   (module
     (func $get_user (param $id i32) (result i32)
       ;; WASM implementation of get logic
       ;; Calls into runtime for DynamoDB access
     )
   )
   ```

2. **VTL template** (for production):
   ```vtl
   {
     "TableName": "users",
     "Key": {
       "id": {
         "S": "$input.params('id')"
       }
     }
   }
   ```

3. **API Gateway config** (CloudFormation):
   ```yaml
   ApiGatewayMethod:
     Type: AWS::ApiGateway::Method
     Properties:
       HttpMethod: GET
       ResourceId: !Ref UsersResource
       AuthorizationType: COGNITO_USER_POOLS
       AuthorizerId: !Ref CognitoAuthorizer
       Integration:
         Type: AWS
         IntegrationHttpMethod: POST
         Uri: !Sub "arn:aws:apigateway:${AWS::Region}:dynamodb:action/GetItem"
         RequestTemplates:
           application/json: !Sub |
             {
               "TableName": "users",
               "Key": {"id": {"S": "$input.params('id')"}}
             }
   ```

### The Critical Guarantee: Local ≡ Production

The WASM runtime must be **semantically isomorphic** to AWS API Gateway:

| Behavior | Local (WASM) | Production (AWS) |
|----------|--------------|------------------|
| Routing | Rust HTTP server | API Gateway |
| Auth | Emulated Cognito | Real Cognito |
| Validation | OpenAPI validator | API Gateway validation |
| Request transform | WASM function | VTL template |
| Data access | Emulated DynamoDB | Real DynamoDB |
| Response | Same format | Same format |
| Errors | Same codes | Same codes |

This means: **If it works locally, it works in production. No "works on my machine" problems.**

## Business Model

**Core principle: Maintainable by 1 developer + LLMs (Claude/ChatGPT)**

### Distribution
- Single compiled binary (Rust-based, ~10-20MB)
- Downloadable from GitHub releases
- Zero-touch installation
- No server infrastructure required
- No support team needed

### Monetization Strategy: Usage-Based Compilation Limits

**Inspired by ChatGPT's model:**

**Free Tier:**
- 30 compilations per month
- Full local development (unlimited `csc dev`)
- Community support (GitHub Discussions)
- Basic cloud resources (Cognito, DynamoDB, API Gateway)
- Single AWS account deployment

**Pro Tier ($15/month):**
- 500 compilations per month
- Advanced security features:
  - Auto WAF policy generation
  - Zero-trust IAM synthesis
  - Advanced rate limiting strategies
- Multi-account deployment
- Advanced CI/CD generation
- Priority GitHub issue responses

**Power Tier ($50/month):**
- Unlimited compilations
- Multi-cloud backends (Azure, GCP via OpenTofu)
- Advanced optimization passes
- Formal verification of IAM policies
- Policy model checking
- Beta features early access

### Why Compilation Limits Work

1. **Natural usage pattern**: Developers don't compile constantly
   - Typical usage: 5-20 compiles/day during active development
   - 30/month = ~1 per day (enough for experimentation)
   - 500/month = ~16 per day (enough for serious projects)

2. **Low support burden**:
   - No "how many users" or "API calls" tracking
   - Simple counter: compile count
   - Reset monthly automatically

3. **Clear value proposition**:
   - Free tier: Try it, learn it, small projects
   - Pro: Serious development work
   - Power: Professional/team usage

4. **Self-serve**: No sales calls, no contracts, no negotiations

### Enforcement Mechanism

```bash
$ csc deploy
✓ Compiling api.py...
✓ Generating CloudFormation...
✗ Error: Compilation limit reached (30/30 this month)

Upgrade to Pro for 500 compiles/month: https://csc.dev/upgrade
Or wait 12 days for free tier reset.
```

**Technical implementation:**
- Signed license token embedded in binary
- Phone-home to license server (lightweight check)
- Cached locally for offline grace period (7 days)
- Anonymous usage UUID (no personal data)
- Open source users can compile from source (removes limits, loses features)

### Licensing Approach
- **Offline-first**: Works without internet for 7 days
- **Signed tokens**: License file downloaded once, validated locally
- **Grace periods**: Deploy failures don't count against limit
- **Compilation = successful deploy**: Failed compiles don't count
- **No DRM on generated code**: Your CloudFormation templates are yours

### Open Source Strategy

**Open (MIT License):**
- Language specification
- Python parser
- AST definition
- Basic AWS backend (API Gateway, DynamoDB, Cognito)
- Local runtime (WASM executor)
- Core compiler pipeline
- Documentation & examples

**Closed (Proprietary):**
- Advanced optimization passes:
  - Cost optimization algorithms
  - Security policy synthesis
  - Performance tuning heuristics
- Multi-cloud backends (Azure, GCP)
- Formal verification engine
- Advanced deployment strategies
- Compilation limit enforcement

**Why this works:**
- Open source builds trust & community
- Closed features provide clear paid value
- Forking open core is easy, forking advanced features is hard
- Community contributions improve base product
- Commercial features stay ahead of forks

### Revenue Projection (Conservative)

**Target: 2,000 paying users**
- 1,500 Pro @ $15/mo = $22,500/mo
- 500 Power @ $50/mo = $25,000/mo
- **Total: $47,500/month ($570k/year)**

**Operating costs:**
- License server: $50/mo (simple API)
- CDN for binaries: $20/mo
- Domain/email: $30/mo
- **Total: ~$100/month**

**Net: $47,400/month with zero employees**

**Achievable because:**
- No support team (community + GitHub Issues)
- No sales team (self-serve)
- No infrastructure team (static binary)
- No DevOps (GitHub Actions for builds)
- Maintenance: 1 developer + LLMs for code generation/debugging

## Competitive Advantages

1. **vs. CDK**: Semantic compilation vs. structural resource declaration
2. **vs. Winglang**: Preserves existing cloud primitives, doesn't hide complexity
3. **vs. Pulumi**: Compiler-based, not library-based
4. **vs. Terraform**: Higher-level abstractions with inferred security
5. **vs. FastAPI on Lambda**: True cloud-native with local dev parity

## Target Users

- Independent developers seeking AWS-native architecture with good DX
- Small teams (1-10 engineers)
- Developers who value correctness and security
- Teams wanting to minimize cloud costs through optimal infrastructure
- Organizations needing compliance-friendly infrastructure

## Success Metrics

- Adoption: 2,000+ paying developers
- Economic viability: ~$40k/month with near-zero marginal cost
- Developer satisfaction: Local dev experience matches or exceeds FastAPI
- Security: Demonstrable reduction in IAM over-permissioning
- Cost: Measurable cloud spend reduction vs. traditional approaches

## Next Steps for Development

1. Define complete semantic primitives
2. Design type system
3. Define policy inference model
4. Design local runtime architecture
5. Implement compiler pipeline stages
6. Build AWS backend code generator
7. Develop local emulation environment
8. Implement feature gating mechanism
9. Build minimal viable product for single cloud backend