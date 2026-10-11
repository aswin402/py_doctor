import ast
import unittest

from py_doctor.rules.async_rules import BlockingIOInAsyncRule, MissingAwaitRule
from py_doctor.rules.database_rules import ConnectionLeakRule, SlowQueryDetectionRule
from py_doctor.rules.fastapi_rules import (
    HardcodedSecretRule,
    MissingResponseModelRule,
    SyncInAsyncRouteRule,
)
from py_doctor.rules.pydantic_rules import MissingValidatorRule, UnsafeFieldRule
from py_doctor.rules.sqlalchemy_rules import (
    MissingAsyncQueryRule,
    MissingSessionCloseRule,
)
from py_doctor.rules.structlog_rules import (
    MissingContextLoggingRule,
    MissingExceptionLoggingRule,
    PrintInsteadLogRule,
)


def parse_and_check(rule_cls, code: str, rel_path: str = "test.py"):
    tree = ast.parse(code)
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


if __name__ == "__main__":
    unittest.main()
