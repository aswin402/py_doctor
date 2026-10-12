import ast
from typing import Any

from py_doctor.constants import SECRET_PATTERNS

from .base_rule import BaseRule


class MissingResponseModelRule(BaseRule):
    rule_id = "fastapi/missing-response-model"
    severity = "WARN"
    description = "Route missing response_model - leaks internal fields and breaks API contract"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if (
                        cls._is_route_decorator(decorator)
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
    def _is_route_decorator(decorator: ast.AST) -> bool:
        return (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in ("get", "post", "put", "delete", "patch", "api_route")
        )

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
            if val.id == "requests" and attr in ("get", "post", "put", "delete", "patch", "request"):
                return True, f"Replace requests.{attr}() with await httpx.AsyncClient().{attr}() or asyncio.to_thread()"
            if val.id == "subprocess" and attr in ("run", "call", "check_output", "check_call"):
                return True, f"Replace subprocess.{attr}() with await asyncio.create_subprocess_exec() or asyncio.to_thread()"
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
                if (
                    any(pattern in name_upper for pattern in SECRET_PATTERNS)
                    and val is not None
                    and cls._is_string_literal(val)
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

    @staticmethod
    def _is_string_literal(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and bool(node.value)
            and not node.value.startswith("${")
            and "os.environ" not in node.value
        )


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
                    if node.args and isinstance(node.args[0], ast.Name) and "CORS" in node.args[0].id:
                        is_cors = True
                    for kw in node.keywords:
                        if kw.arg == "middleware" and isinstance(kw.value, ast.Name) and "CORS" in kw.value.id:
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
    description = "Mutable default argument (list/dict/set) in route handler leaks state across requests"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_route = any(cls._is_route_decorator(d) for d in node.decorator_list)
                if not is_route:
                    continue

                all_defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]
                for default_node in all_defaults:
                    if isinstance(default_node, (ast.List, ast.Dict, ast.Set)):
                        type_name = "list" if isinstance(default_node, ast.List) else "dict" if isinstance(default_node, ast.Dict) else "set"
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

    @staticmethod
    def _is_route_decorator(decorator: ast.AST) -> bool:
        return (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in ("get", "post", "put", "delete", "patch", "api_route")
        )


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
                    if (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr in ("get", "post", "put", "delete", "patch", "api_route")
                    ):
                        path_str = None
                        path_node = None
                        if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                            path_str = decorator.args[0].value
                            path_node = decorator.args[0]
                        else:
                            for kw in decorator.keywords:
                                if kw.arg == "path" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
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

