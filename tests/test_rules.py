import ast
import unittest

from py_doctor.rules.ast_utils import annotate_parents
from py_doctor.rules.async_rules import BlockingIOInAsyncRule, MissingAwaitRule
from py_doctor.rules.database_rules import (
    ConnectionLeakRule,
    MissingPoolConfigRule,
    NPlusOneQueryRule,
    SlowQueryDetectionRule,
    TransactionManagementRule,
)
from py_doctor.rules.fastapi_rules import (
    BackgroundTaskDBSessionRule,
    BareExceptSwallowRule,
    HardcodedSecretRule,
    InsecureCORSRule,
    InvalidRoutePathRule,
    MissingResponseModelRule,
    MutableDefaultArgumentRule,
    Status204WithBodyRule,
    SyncInAsyncRouteRule,
)
from py_doctor.rules.pydantic_rules import (
    MissingFieldDefaultsRule,
    MissingValidatorRule,
    PydanticV1DumpRule,
    PydanticV1ValidatorRule,
    UnsafeFieldRule,
)
from py_doctor.rules.sqlalchemy_rules import (
    MissingAsyncQueryRule,
    MissingIndexRule,
    MissingSessionCloseRule,
)
from py_doctor.rules.sqlalchemy_rules import (
    NPlusOneQueryRule as SqlAlchemyNPlusOneQueryRule,
)
from py_doctor.rules.structlog_rules import (
    MissingContextLoggingRule,
    MissingExceptionLoggingRule,
    PrintInsteadLogRule,
)


def parse_and_check(rule_cls, code: str, rel_path: str = "test.py"):
    tree = ast.parse(code)
    annotate_parents(tree)
    return rule_cls.check(tree, code, rel_path)


class TestRules(unittest.TestCase):
    # FastAPI Rules
    def test_missing_response_model(self):
        bad_code = """
@app.get("/items")
async def get_items():
    return [{"id": 1}]
"""
        diags = parse_and_check(MissingResponseModelRule, bad_code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "fastapi/missing-response-model")

        good_code = """
@app.get("/items", response_model=list[Item])
async def get_items():
    return [{"id": 1}]
"""
        self.assertEqual(len(parse_and_check(MissingResponseModelRule, good_code)), 0)

        annotated_return_code = """
@app.get("/items")
async def get_items() -> list[Item]:
    return [{"id": 1}]
"""
        self.assertEqual(len(parse_and_check(MissingResponseModelRule, annotated_return_code)), 0)

    def test_sync_in_async_route(self):
        bad_code = """
async def handler():
    time.sleep(1)
"""
        diags = parse_and_check(SyncInAsyncRouteRule, bad_code)
        self.assertEqual(len(diags), 1)

        good_code = """
async def handler():
    await asyncio.sleep(1)
"""
        self.assertEqual(len(parse_and_check(SyncInAsyncRouteRule, good_code)), 0)

    def test_hardcoded_secret(self):
        bad_code = 'SECRET_KEY = "super-secret-key-12345"'
        diags = parse_and_check(HardcodedSecretRule, bad_code)
        self.assertEqual(len(diags), 1)

        bad_annotated = 'SECRET_KEY: str = "super-secret-key-12345"'
        self.assertEqual(len(parse_and_check(HardcodedSecretRule, bad_annotated)), 1)

        good_code = 'SECRET_KEY = os.environ.get("SECRET_KEY")'
        self.assertEqual(len(parse_and_check(HardcodedSecretRule, good_code)), 0)

    # Async Rules
    def test_missing_await_rule(self):
        bad_code = """
async def fetch_user():
    db.execute("SELECT 1")
"""
        diags = parse_and_check(MissingAwaitRule, bad_code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "async/missing-await")

        # Correctly awaited execute
        good_code = """
async def fetch_user():
    await db.execute("SELECT 1")
"""
        self.assertEqual(len(parse_and_check(MissingAwaitRule, good_code)), 0)

        # Standard dict.get should NOT be flagged!
        dict_code = """
async def handler():
    data = {"key": "val"}
    x = data.get("key")
"""
        self.assertEqual(len(parse_and_check(MissingAwaitRule, dict_code)), 0)

    def test_blocking_io_in_async(self):
        code = """
async def read_file():
    f = open("data.txt")
"""
        diags = parse_and_check(BlockingIOInAsyncRule, code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "async/blocking-io")

    # SQLAlchemy Rules
    def test_missing_session_close(self):
        bad_code = """
def run_query():
    s = Session()
    s.query(User)
"""
        diags = parse_and_check(MissingSessionCloseRule, bad_code)
        self.assertEqual(len(diags), 1)

        good_code = """
def run_query():
    s = Session()
    try:
        pass
    finally:
        s.close()
"""
        self.assertEqual(len(parse_and_check(MissingSessionCloseRule, good_code)), 0)

    def test_missing_async_query_rule(self):
        # Awaited execute in async session is valid SQLAlchemy 2.0
        good_async_exec = """
async def get_users():
    result = await session.execute(stmt)
"""
        self.assertEqual(len(parse_and_check(MissingAsyncQueryRule, good_async_exec)), 0)

        # Blocking 1.x Query call on db
        bad_sync_query = """
async def get_users():
    users = db.query(User).all()
"""
        diags = parse_and_check(MissingAsyncQueryRule, bad_sync_query)
        self.assertTrue(len(diags) >= 1)

    # Database Rules
    def test_connection_leak_with_context_manager(self):
        # Context manager handles acquire and release automatically
        ctx_code = """
async def query_db():
    async with pool.acquire() as conn:
        await conn.execute("SELECT 1")
"""
        self.assertEqual(len(parse_and_check(ConnectionLeakRule, ctx_code)), 0)

        # Unbalanced acquire without release
        unbalanced_code = """
async def query_db():
    conn = pool.acquire()
"""
        diags = parse_and_check(ConnectionLeakRule, unbalanced_code)
        self.assertEqual(len(diags), 1)

    def test_slow_query_detection(self):
        bad_code = """
def load_all():
    return session.query(User).all()
"""
        diags = parse_and_check(SlowQueryDetectionRule, bad_code)
        self.assertEqual(len(diags), 1)

        good_code = """
def load_limited():
    return session.query(User).limit(10).all()
"""
        self.assertEqual(len(parse_and_check(SlowQueryDetectionRule, good_code)), 0)

    # Pydantic Rules
    def test_unsafe_field(self):
        bad_annotated = """
class AuthModel(BaseModel):
    jwt_secret: str = "hardcoded-secret"
"""
        diags = parse_and_check(UnsafeFieldRule, bad_annotated)
        self.assertEqual(len(diags), 1)

        good_model = """
class AuthModel(BaseModel):
    jwt_secret: SecretStr
"""
        self.assertEqual(len(parse_and_check(UnsafeFieldRule, good_model)), 0)

    def test_missing_validator_rule(self):
        unvalidated = """
class UserModel(BaseModel):
    email: str
"""
        diags = parse_and_check(MissingValidatorRule, unvalidated)
        self.assertEqual(len(diags), 1)

        validated_email_str = """
class UserModel(BaseModel):
    email: EmailStr
"""
        self.assertEqual(len(parse_and_check(MissingValidatorRule, validated_email_str)), 0)

    # Structlog Rules
    def test_print_instead_of_log(self):
        bad_code = """
def process():
    print("processing started")
"""
        diags = parse_and_check(PrintInsteadLogRule, bad_code, "app/services.py")
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "structlog/print-instead-of-log")

        # Skipped in cli/reporter/main files
        self.assertEqual(len(parse_and_check(PrintInsteadLogRule, bad_code, "cli.py")), 0)
        self.assertEqual(len(parse_and_check(PrintInsteadLogRule, bad_code, "app/main.py")), 0)

    def test_missing_context_logging(self):
        bad_code = """
def handle_request(user_id):
    logger.info("processing request")
"""
        diags = parse_and_check(MissingContextLoggingRule, bad_code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "structlog/missing-context")

        good_code = """
def handle_request(user_id):
    log = logger.bind(user_id=user_id)
    log.info("processing request")
"""
        self.assertEqual(len(parse_and_check(MissingContextLoggingRule, good_code)), 0)

    def test_missing_exception_logging(self):
        bad_code = """
try:
    risky_operation()
except Exception:
    pass
"""
        diags = parse_and_check(MissingExceptionLoggingRule, bad_code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "structlog/missing-exception")

        good_code = """
try:
    risky_operation()
except Exception:
    logger.exception("Operation failed")
"""
        self.assertEqual(len(parse_and_check(MissingExceptionLoggingRule, good_code)), 0)

    def test_insecure_cors(self):
        bad_code = """
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
)
"""
        diags = parse_and_check(InsecureCORSRule, bad_code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "fastapi/insecure-cors")

        good_code = """
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],
    allow_credentials=True,
)
"""
        self.assertEqual(len(parse_and_check(InsecureCORSRule, good_code)), 0)

        good_wildcard_no_creds = """
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
)
"""
        self.assertEqual(len(parse_and_check(InsecureCORSRule, good_wildcard_no_creds)), 0)

    def test_bare_except_swallow(self):
        bad_code = """
try:
    do_something()
except Exception:
    pass
"""
        diags = parse_and_check(BareExceptSwallowRule, bad_code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "fastapi/bare-except-swallow")

        good_code = """
try:
    do_something()
except Exception as e:
    logger.exception("Failed to do something")
"""
        self.assertEqual(len(parse_and_check(BareExceptSwallowRule, good_code)), 0)

    def test_n_plus_one_query(self):
        bad_code = """
def fetch_users(user_ids):
    for u_id in user_ids:
        user = session.execute(select(User).where(User.id == u_id))
"""
        diags = parse_and_check(NPlusOneQueryRule, bad_code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "database/n-plus-one-query")

        good_code = """
def fetch_users(user_ids):
    users = session.execute(select(User).where(User.id.in_(user_ids)))
"""
        self.assertEqual(len(parse_and_check(NPlusOneQueryRule, good_code)), 0)

    def test_sync_in_async_route_requests(self):
        code = """
@app.get("/data")
async def fetch_remote():
    res = requests.get("https://api.example.com")
    return res.json()
"""
        diags = parse_and_check(SyncInAsyncRouteRule, code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "fastapi/sync-in-async-route")
        self.assertIn("httpx.AsyncClient", diags[0]["suggestion"])

    def test_blocking_io_in_async_requests(self):
        code = """
async def do_sync_post():
    requests.post("https://api.example.com", json={})
"""
        diags = parse_and_check(BlockingIOInAsyncRule, code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "async/blocking-io")

    def test_mutable_default_argument(self):
        bad_code = """
@app.get("/items")
async def get_items(tags: list = [], options: dict = {}):
    return {"tags": tags}
"""
        diags = parse_and_check(MutableDefaultArgumentRule, bad_code)
        self.assertEqual(len(diags), 2)
        self.assertEqual(diags[0]["rule"], "fastapi/mutable-default-argument")

        good_code = """
@app.get("/items")
async def get_items(tags: list = None, options: dict = None):
    tags = tags or []
    return {"tags": tags}
"""
        self.assertEqual(len(parse_and_check(MutableDefaultArgumentRule, good_code)), 0)

    def test_invalid_route_path(self):
        missing_slash = """
@app.get("items")
async def get_items():
    return []
"""
        diags = parse_and_check(InvalidRoutePathRule, missing_slash)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "fastapi/invalid-route-path")
        self.assertIn("missing leading '/'", diags[0]["description"])

        double_slash = """
@app.get("//items/detail")
async def get_detail():
    return {}
"""
        diags2 = parse_and_check(InvalidRoutePathRule, double_slash)
        self.assertEqual(len(diags2), 1)
        self.assertIn("contains duplicate slashes", diags2[0]["description"])

        valid_path = """
@app.get("/items")
async def get_items():
    return []
"""
        self.assertEqual(len(parse_and_check(InvalidRoutePathRule, valid_path)), 0)

    def test_transaction_management_no_false_positives(self):
        # Benign dictionary update and list insert MUST NOT be flagged as missing DB transactions
        dict_update_code = """
def update_profile(data: dict):
    local_map = {}
    local_map.update(data)
    local_map.update({"status": "active"})
    return local_map
"""
        self.assertEqual(len(parse_and_check(TransactionManagementRule, dict_update_code)), 0)

        list_insert_code = """
def prepend_item(items: list):
    items.insert(0, "first_item")
    return items
"""
        self.assertEqual(len(parse_and_check(TransactionManagementRule, list_insert_code)), 0)

    def test_transaction_management_detects_uncommitted_db_write(self):
        # Real DB write without commit/rollback should be flagged
        bad_code = """
def update_user_status(user_id: int):
    session.execute("UPDATE users SET active = 1 WHERE id = :id", {"id": user_id})
"""
        diags = parse_and_check(TransactionManagementRule, bad_code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "database/transaction-management")

        # Protected by context manager or commit should not be flagged
        good_code = """
def update_user_status(user_id: int):
    with session.begin():
        session.execute("UPDATE users SET active = 1 WHERE id = :id", {"id": user_id})
"""
        self.assertEqual(len(parse_and_check(TransactionManagementRule, good_code)), 0)

    def test_n_plus_one_dict_get_not_flagged(self):
        # dict.get inside a loop MUST NOT be flagged as an N+1 query
        dict_get_code = """
def lookup_cache(user_ids, cache):
    results = []
    for uid in user_ids:
        cached = cache.get(uid)
        results.append(cached)
    return results
"""
        self.assertEqual(len(parse_and_check(SqlAlchemyNPlusOneQueryRule, dict_get_code)), 0)
        self.assertEqual(len(parse_and_check(NPlusOneQueryRule, dict_get_code)), 0)

    def test_sqlalchemy_n_plus_one_detected(self):
        bad_code = """
def fetch_users(user_ids):
    results = []
    for uid in user_ids:
        u = session.query(User).filter_by(id=uid).first()
        results.append(u)
    return results
"""
        diags = parse_and_check(SqlAlchemyNPlusOneQueryRule, bad_code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "sqlalchemy/n-plus-one")

    def test_hardcoded_secret_safe_keys_excluded(self):
        # Benign constants with KEY in them MUST NOT trigger false alarms
        safe_code = """
CACHE_KEY = "user_profile_cache"
PRIMARY_KEY = "record_id"
PUBLIC_KEY = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC"
SORT_KEY = "created_at_desc"
"""
        self.assertEqual(len(parse_and_check(HardcodedSecretRule, safe_code)), 0)

    def test_unsafe_field_safe_keys_and_settings(self):
        # Safe fields on BaseModel
        safe_model = """
class CacheEntry(BaseModel):
    primary_key: str = "id"
    cache_key: str = "prefix"
    public_key: str = "pub_123"
"""
        self.assertEqual(len(parse_and_check(UnsafeFieldRule, safe_model)), 0)

        # BaseSettings with sensitive field default MUST be flagged
        settings_code = """
class AppSettings(BaseSettings):
    api_key: str = "raw-secret-token-abc"
"""
        diags = parse_and_check(UnsafeFieldRule, settings_code)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "pydantic/unsafe-field")

    def test_missing_index_modern_and_legacy(self):
        # Legacy Column without index
        legacy_bad = """
class Order(Base):
    customer_id = Column(Integer, ForeignKey("customers.id"))
"""
        diags = parse_and_check(MissingIndexRule, legacy_bad)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "sqlalchemy/missing-index")

        # Modern SQLAlchemy 2.0 mapped_column without index
        modern_bad = """
class Order(Base):
    customer_id = mapped_column(Integer, ForeignKey("customers.id"))
"""
        diags = parse_and_check(MissingIndexRule, modern_bad)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "sqlalchemy/missing-index")

        # With index=True should NOT be flagged
        indexed_good = """
class Order(Base):
    customer_id = mapped_column(Integer, ForeignKey("customers.id"), index=True)
"""
        self.assertEqual(len(parse_and_check(MissingIndexRule, indexed_good)), 0)

    def test_missing_pool_config(self):
        # Production DB without pool config
        bad_engine = """
engine = create_engine("postgresql://user:pass@localhost:5432/mydb")
"""
        diags = parse_and_check(MissingPoolConfigRule, bad_engine)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "database/missing-pool-config")

        # Configured pool
        good_engine = """
engine = create_engine("postgresql://user:pass@localhost:5432/mydb", pool_size=10, max_overflow=20)
"""
        self.assertEqual(len(parse_and_check(MissingPoolConfigRule, good_engine)), 0)

        # SQLite should be skipped
        sqlite_engine = """
engine = create_engine("sqlite:///local.db")
"""
        self.assertEqual(len(parse_and_check(MissingPoolConfigRule, sqlite_engine)), 0)

    def test_missing_field_defaults(self):
        model_code = """
class UserCreate(BaseModel):
    username: str
    password: str
"""
        diags = parse_and_check(MissingFieldDefaultsRule, model_code)
        self.assertEqual(len(diags), 2)
        self.assertEqual(diags[0]["rule"], "pydantic/missing-field-defaults")

    def test_background_task_db_session(self):
        # Passing request-scoped db session to background task should be flagged
        bad_code_1 = """
@app.post("/users")
def create_user(user_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(send_welcome_email, db, user_id)
"""
        diags = parse_and_check(BackgroundTaskDBSessionRule, bad_code_1)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "fastapi/background-task-db-session")
        self.assertEqual(diags[0]["type"], "ERR")
        self.assertIn("session", diags[0]["suggestion"])

        # Passing keyword arg session=db
        bad_code_2 = """
@app.post("/audit")
def audit_event(event_id: str, bg: BackgroundTasks, session: Session = Depends(get_db)):
    bg.add_task(record_audit, event_id=event_id, db=session)
"""
        diags2 = parse_and_check(BackgroundTaskDBSessionRule, bad_code_2)
        self.assertEqual(len(diags2), 1)
        self.assertEqual(diags2[0]["rule"], "fastapi/background-task-db-session")

        # Passing non-DB arguments to background task should NOT be flagged
        good_code = """
@app.post("/users")
def create_user(user_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(send_welcome_email, user_id, email="test@example.com")
"""
        self.assertEqual(len(parse_and_check(BackgroundTaskDBSessionRule, good_code)), 0)

    def test_status_204_with_body(self):
        # 204 route with response_model should be flagged
        bad_resp_model = """
@app.delete("/items/{item_id}", status_code=204, response_model=ItemSchema)
def delete_item(item_id: int):
    return None
"""
        diags = parse_and_check(Status204WithBodyRule, bad_resp_model)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "fastapi/status-204-with-body")
        self.assertIn("response_model", diags[0]["description"])

        # 204 route returning a payload body should be flagged
        bad_body = """
@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    return {"message": "item deleted"}
"""
        diags2 = parse_and_check(Status204WithBodyRule, bad_body)
        self.assertEqual(len(diags2), 1)
        self.assertEqual(diags2[0]["rule"], "fastapi/status-204-with-body")
        self.assertIn("returns a response body", diags2[0]["description"])

        # 204 route returning None or Response should NOT be flagged
        good_none = """
@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    # do cleanup
    return None
"""
        self.assertEqual(len(parse_and_check(Status204WithBodyRule, good_none)), 0)

        good_response = """
@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    return Response(status_code=204)
"""
        self.assertEqual(len(parse_and_check(Status204WithBodyRule, good_response)), 0)

        # Non-204 route returning a body should NOT be flagged by this rule
        good_200 = """
@app.get("/items/{item_id}", status_code=200, response_model=ItemSchema)
def get_item(item_id: int):
    return {"id": item_id}
"""
        self.assertEqual(len(parse_and_check(Status204WithBodyRule, good_200)), 0)

    def test_pydantic_v1_deprecated_validator(self):
        # @validator on BaseModel should be flagged
        code_validator = """
from pydantic import BaseModel, validator

class UserModel(BaseModel):
    name: str

    @validator("name")
    def name_must_not_be_empty(cls, v):
        if not v:
            raise ValueError("empty")
        return v
"""
        diags = parse_and_check(PydanticV1ValidatorRule, code_validator)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "pydantic/v1-deprecated-validator")
        self.assertIn("@field_validator", diags[0]["suggestion"])

        # @root_validator on BaseModel should be flagged
        code_root_validator = """
from pydantic import BaseModel, root_validator

class ConfigModel(BaseModel):
    a: int
    b: int

    @root_validator
    def check_values(cls, values):
        return values
"""
        diags2 = parse_and_check(PydanticV1ValidatorRule, code_root_validator)
        self.assertEqual(len(diags2), 1)
        self.assertEqual(diags2[0]["rule"], "pydantic/v1-deprecated-validator")
        self.assertIn("@model_validator", diags2[0]["suggestion"])

        # Pydantic v2 modern validators should NOT be flagged
        modern_code = """
from pydantic import BaseModel, field_validator, model_validator

class ModernModel(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def validate_model(self):
        return self
"""
        self.assertEqual(len(parse_and_check(PydanticV1ValidatorRule, modern_code)), 0)

    def test_pydantic_v1_deprecated_dump(self):
        # .dict(exclude_unset=True) with pydantic keyword argument should be flagged
        code_with_kwargs = """
from pydantic import BaseModel

class User(BaseModel):
    id: int

def export(user: User):
    return user.dict(exclude_unset=True)
"""
        diags = parse_and_check(PydanticV1DumpRule, code_with_kwargs)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["rule"], "pydantic/v1-deprecated-dump")
        self.assertIn(".model_dump()", diags[0]["description"])

        # self.dict() inside a Pydantic model should be flagged
        code_self_dict = """
from pydantic import BaseModel

class User(BaseModel):
    name: str

    def to_dict(self):
        return self.dict()
"""
        diags2 = parse_and_check(PydanticV1DumpRule, code_self_dict)
        self.assertEqual(len(diags2), 1)
        self.assertEqual(diags2[0]["rule"], "pydantic/v1-deprecated-dump")

        # user.dict() on typed parameter should be flagged
        code_param_dict = """
from pydantic import BaseModel

def save_user(user: UserModel):
    data = user.dict()
"""
        diags3 = parse_and_check(PydanticV1DumpRule, code_param_dict)
        self.assertEqual(len(diags3), 1)
        self.assertEqual(diags3[0]["rule"], "pydantic/v1-deprecated-dump")

        # Modern .model_dump() should NOT be flagged
        modern_dump = """
from pydantic import BaseModel

def save_user(user: UserModel):
    data = user.model_dump(exclude_unset=True)
"""
        self.assertEqual(len(parse_and_check(PydanticV1DumpRule, modern_dump)), 0)

        # Standard dictionary should NOT be flagged
        std_dict = """
my_map = {"a": 1, "b": 2}
val = my_map.get("a")
items = my_map.items()
"""
        self.assertEqual(len(parse_and_check(PydanticV1DumpRule, std_dict)), 0)


if __name__ == "__main__":
    unittest.main()
