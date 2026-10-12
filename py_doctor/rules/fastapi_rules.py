import ast
from typing import Any

from py_doctor.constants import SAFE_KEY_EXCLUSIONS, SECRET_PATTERNS

from .ast_utils import (
    annotate_parents,
    is_db_caller,
    is_route_decorator,
    is_string_literal,
)
from .base_rule import BaseRule


class MissingResponseModelRule(BaseRule):
    rule_id = "fastapi/missing-response-model"
    severity = "WARN"
    description = "Route missing response_model - leaks internal fields and breaks API contract"

    _is_route_decorator = staticmethod(is_route_decorator)

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if (
                        is_route_decorator(decorator)
                        and not cls._has_response_model(decorator)
                        and node.returns is None
                    ):
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{node.lineno}",
                                "description": cls.description,
                                "suggestion": "Add response_model=... or return type annotation (-> ResponseModel)",
                            }
                        )
        return diagnostics

    @staticmethod
    def _has_response_model(decorator: ast.AST) -> bool:
        if not isinstance(decorator, ast.Call):
            return False
        return any(kw.arg == "response_model" for kw in decorator.keywords)


class SyncInAsyncRouteRule(BaseRule):
    rule_id = "fastapi/sync-in-async-route"
    severity = "ERR"
    description = "Blocking call in async route blocks the entire event loop"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    is_blocking, suggestion = cls._check_blocking_call(child)
                    if is_blocking:
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{getattr(child, 'lineno', 1)}",
                                "description": cls.description,
                                "suggestion": suggestion,
                            }
                        )
        return diagnostics

    @classmethod
    def _check_blocking_call(cls, node: ast.AST) -> tuple[bool, str]:
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            return False, ""
        val = getattr(node.func, "value", None)
        attr = node.func.attr
        if isinstance(val, ast.Name):
            if val.id == "time" and attr == "sleep":
                return True, "Replace time.sleep() with await asyncio.sleep()"
            if val.id == "requests" and attr in (
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "request",
            ):
                return (
                    True,
                    f"Replace requests.{attr}() with await httpx.AsyncClient().{attr}() or asyncio.to_thread()",
                )
            if val.id == "subprocess" and attr in ("run", "call", "check_output", "check_call"):
                return (
                    True,
                    f"Replace subprocess.{attr}() with await asyncio.create_subprocess_exec() or asyncio.to_thread()",
                )
        return False, ""

    @staticmethod
    def _is_time_sleep(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sleep"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "time"
        )


class HardcodedSecretRule(BaseRule):
    rule_id = "fastapi/hardcoded-secret"
    severity = "ERR"
    description = "Hardcoded secret in source code - security risk"

    _is_string_literal = staticmethod(is_string_literal)

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            assignments: list[tuple[str, Any, int]] = []
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments.append((target.id, node.value, getattr(node, "lineno", 1)))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                assignments.append((node.target.id, node.value, getattr(node, "lineno", 1)))

            for name, val, lineno in assignments:
                name_upper = name.upper()
                if any(
                    safe == name_upper
                    or name_upper.endswith(f"_{safe}")
                    or name_upper.startswith(f"{safe}_")
                    for safe in SAFE_KEY_EXCLUSIONS
                ):
                    continue
                if (
                    any(pattern in name_upper for pattern in SECRET_PATTERNS)
                    and val is not None
                    and is_string_literal(val)
                ):
                    diagnostics.append(
                        {
                            "type": cls.severity,
                            "rule": cls.rule_id,
                            "location": f"{rel_path}:{lineno}",
                            "description": cls.description,
                            "suggestion": f"Move {name} to environment variable using pydantic-settings",
                        }
                    )
        return diagnostics


class InsecureCORSRule(BaseRule):
    rule_id = "fastapi/insecure-cors"
    severity = "ERR"
    description = "Insecure CORS configuration: allow_origins=['*'] with allow_credentials=True violates CORS spec and introduces security risks"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                is_cors = False
                if isinstance(node.func, ast.Attribute) and node.func.attr == "add_middleware":
                    if (
                        node.args
                        and isinstance(node.args[0], ast.Name)
                        and "CORS" in node.args[0].id
                    ):
                        is_cors = True
                    for kw in node.keywords:
                        if (
                            kw.arg == "middleware"
                            and isinstance(kw.value, ast.Name)
                            and "CORS" in kw.value.id
                        ):
                            is_cors = True
                elif isinstance(node.func, ast.Name) and "CORS" in node.func.id:
                    is_cors = True

                if is_cors:
                    has_wildcard_origin = False
                    has_credentials_true = False
                    for kw in node.keywords:
                        if kw.arg == "allow_origins":
                            if isinstance(kw.value, ast.List):
                                for elt in kw.value.elts:
                                    if isinstance(elt, ast.Constant) and elt.value == "*":
                                        has_wildcard_origin = True
                            elif isinstance(kw.value, ast.Constant) and kw.value.value == "*":
                                has_wildcard_origin = True
                        elif (
                            kw.arg == "allow_credentials"
                            and isinstance(kw.value, ast.Constant)
                            and kw.value.value is True
                        ):
                            has_credentials_true = True

                    if has_wildcard_origin and has_credentials_true:
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                                "description": cls.description,
                                "suggestion": "Specify explicit origins (e.g. ['https://example.com']) or set allow_credentials=False",
                            }
                        )
        return diagnostics


class BareExceptSwallowRule(BaseRule):
    rule_id = "fastapi/bare-except-swallow"
    severity = "WARN"
    description = "Exception swallowed silently with pass - hides failures and hinders debugging"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and len(node.body) == 1:
                first_stmt = node.body[0]
                is_empty = isinstance(first_stmt, ast.Pass) or (
                    isinstance(first_stmt, ast.Expr)
                    and isinstance(first_stmt.value, ast.Constant)
                    and first_stmt.value.value is Ellipsis
                )
                if is_empty:
                    diagnostics.append(
                        {
                            "type": cls.severity,
                            "rule": cls.rule_id,
                            "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                            "description": cls.description,
                            "suggestion": "Log the exception with logger.exception() or re-raise an HTTPException",
                        }
                    )
        return diagnostics


class MutableDefaultArgumentRule(BaseRule):
    rule_id = "fastapi/mutable-default-argument"
    severity = "ERR"
    description = (
        "Mutable default argument (list/dict/set) in route handler leaks state across requests"
    )

    _is_route_decorator = staticmethod(is_route_decorator)

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_route = any(is_route_decorator(d) for d in node.decorator_list)
                if not is_route:
                    continue

                all_defaults = list(node.args.defaults) + [
                    d for d in node.args.kw_defaults if d is not None
                ]
                for default_node in all_defaults:
                    if isinstance(default_node, (ast.List, ast.Dict, ast.Set)):
                        type_name = (
                            "list"
                            if isinstance(default_node, ast.List)
                            else "dict"
                            if isinstance(default_node, ast.Dict)
                            else "set"
                        )
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{getattr(default_node, 'lineno', node.lineno)}",
                                "description": cls.description,
                                "suggestion": f"Use None as default ({type_name} = None) and initialize inside handler",
                            }
                        )
        return diagnostics


class InvalidRoutePathRule(BaseRule):
    rule_id = "fastapi/invalid-route-path"
    severity = "WARN"
    description = "Route path missing leading slash or contains duplicate slashes"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if is_route_decorator(decorator) and isinstance(decorator, ast.Call):
                        path_str = None
                        path_node = None
                        if (
                            decorator.args
                            and isinstance(decorator.args[0], ast.Constant)
                            and isinstance(decorator.args[0].value, str)
                        ):
                            path_str = decorator.args[0].value
                            path_node = decorator.args[0]
                        else:
                            for kw in decorator.keywords:
                                if (
                                    kw.arg == "path"
                                    and isinstance(kw.value, ast.Constant)
                                    and isinstance(kw.value.value, str)
                                ):
                                    path_str = kw.value.value
                                    path_node = kw.value
                                    break

                        if path_str is not None:
                            lineno = getattr(path_node, "lineno", node.lineno)
                            if not path_str.startswith("/"):
                                diagnostics.append(
                                    {
                                        "type": cls.severity,
                                        "rule": cls.rule_id,
                                        "location": f"{rel_path}:{lineno}",
                                        "description": f"Route path '{path_str}' missing leading '/'",
                                        "suggestion": f"Change path to '/{path_str}'",
                                    }
                                )
                            elif "//" in path_str:
                                cleaned = "/" + "/".join(filter(None, path_str.split("/")))
                                diagnostics.append(
                                    {
                                        "type": cls.severity,
                                        "rule": cls.rule_id,
                                        "location": f"{rel_path}:{lineno}",
                                        "description": f"Route path '{path_str}' contains duplicate slashes '//'",
                                        "suggestion": f"Change path to '{cleaned}'",
                                    }
                                )
        return diagnostics


class BackgroundTaskDBSessionRule(BaseRule):
    rule_id = "fastapi/background-task-db-session"
    severity = "ERR"
    description = (
        "Request-scoped database session passed to BackgroundTasks — session will be closed "
        "when response finishes, causing closed connection errors or connection pool leaks"
    )

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        annotate_parents(tree)

        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_task"
            ):
                continue

            # Determine if caller represents BackgroundTasks
            is_bg = False
            caller = node.func.value

            bg_names = {"background_tasks", "background_task", "tasks", "bg_tasks", "bg"}

            if (isinstance(caller, ast.Name) and caller.id.lower() in bg_names) or (
                isinstance(caller, ast.Attribute) and caller.attr.lower() in bg_names
            ):
                is_bg = True
            elif isinstance(caller, ast.Call):
                func = caller.func
                func_name = getattr(func, "id", "") or getattr(func, "attr", "")
                if "BackgroundTasks" in func_name:
                    is_bg = True

            if not is_bg and isinstance(caller, ast.Name):
                # Check if caller was type-annotated as BackgroundTasks in enclosing function
                curr: Any = getattr(node, "parent", None)
                while curr is not None:
                    if isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for param in curr.args.args + curr.args.kwonlyargs:
                            if (
                                param.arg == caller.id
                                and param.annotation
                                and "BackgroundTasks" in ast.unparse(param.annotation)
                            ):
                                is_bg = True
                        break
                    curr = getattr(curr, "parent", None)

            if not is_bg:
                continue

            # Check positional arguments (after function) and keyword arguments
            passed_args = node.args[1:] + [kw.value for kw in node.keywords]
            for passed_arg in passed_args:
                if cls._is_db_resource(passed_arg):
                    arg_name = "session"
                    if isinstance(passed_arg, ast.Name):
                        arg_name = f"'{passed_arg.id}'"
                    elif isinstance(passed_arg, ast.Attribute):
                        arg_name = f"'{passed_arg.attr}'"
                    elif isinstance(passed_arg, ast.Call):
                        fn_name = getattr(passed_arg.func, "id", "") or getattr(
                            passed_arg.func, "attr", ""
                        )
                        arg_name = f"'{fn_name}()'"

                    diagnostics.append(
                        {
                            "type": cls.severity,
                            "rule": cls.rule_id,
                            "location": f"{rel_path}:{node.lineno}",
                            "description": cls.description,
                            "suggestion": (
                                f"Do not pass request-scoped database resource {arg_name} to background tasks. "
                                "Create a fresh database session inside the background task worker function instead."
                            ),
                        }
                    )
                    break

        return diagnostics

    @classmethod
    def _is_db_resource(cls, node: ast.AST) -> bool:
        if is_db_caller(node):
            return True
        if isinstance(node, ast.Call):
            if is_db_caller(node.func):
                return True
            fn_name = (getattr(node.func, "id", "") or getattr(node.func, "attr", "")).lower()
            if any(term in fn_name for term in ("session", "db", "conn")):
                return True
        return False


class Status204WithBodyRule(BaseRule):
    rule_id = "fastapi/status-204-with-body"
    severity = "WARN"
    description = "Route with status code 204 (No Content) should not declare a response_model or return a body (RFC 9110 violation)"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for decorator in node.decorator_list:
                if not is_route_decorator(decorator) or not isinstance(decorator, ast.Call):
                    continue

                if not cls._is_status_204(decorator):
                    continue

                # 1. Check for response_model
                for kw in decorator.keywords:
                    if kw.arg == "response_model" and not (
                        isinstance(kw.value, ast.Constant) and kw.value.value is None
                    ):
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{decorator.lineno}",
                                "description": (
                                    "Route with status code 204 (No Content) declares response_model "
                                    "— RFC 9110 Section 6.3.5 forbids a message body in 204 responses"
                                ),
                                "suggestion": "Remove response_model=... from the route decorator or use status code 200/202",
                            }
                        )

                # 2. Check returns inside function body
                for ret in cls._get_function_returns(node):
                    if cls._returns_body(ret):
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{ret.lineno}",
                                "description": (
                                    "Route with status code 204 (No Content) returns a response body "
                                    "— RFC 9110 Section 6.3.5 forbids a message body in 204 responses"
                                ),
                                "suggestion": (
                                    "Return None or fastapi.Response(status_code=status.HTTP_204_NO_CONTENT) "
                                    "instead of returning data"
                                ),
                            }
                        )

        return diagnostics

    @classmethod
    def _is_status_204(cls, decorator: ast.Call) -> bool:
        for kw in decorator.keywords:
            if kw.arg == "status_code":
                if isinstance(kw.value, ast.Constant) and kw.value.value == 204:
                    return True
                if isinstance(kw.value, ast.Attribute) and kw.value.attr in (
                    "HTTP_204_NO_CONTENT",
                    "NO_CONTENT",
                ):
                    return True
                if isinstance(kw.value, ast.Name) and kw.value.id in (
                    "HTTP_204_NO_CONTENT",
                    "NO_CONTENT",
                ):
                    return True
        return False

    @staticmethod
    def _get_function_returns(fn_node: ast.AST) -> list[ast.Return]:
        returns: list[ast.Return] = []
        stack: list[ast.AST] = list(ast.iter_child_nodes(fn_node))
        while stack:
            curr = stack.pop()
            if isinstance(curr, ast.Return):
                returns.append(curr)
            elif not isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                stack.extend(ast.iter_child_nodes(curr))
        return returns

    @classmethod
    def _returns_body(cls, ret_node: ast.Return) -> bool:
        if ret_node.value is None:
            return False
        if isinstance(ret_node.value, ast.Constant) and ret_node.value.value is None:
            return False
        if isinstance(ret_node.value, ast.Name) and ret_node.value.id in ("None",):
            return False
        # Allow Response(...) or Response(status_code=204)
        if isinstance(ret_node.value, ast.Call):
            func = ret_node.value.func
            func_name = getattr(func, "id", "") or getattr(func, "attr", "")
            if func_name == "Response":
                return False
        return True
