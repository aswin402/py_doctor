"""High-performance JSON serialization & parsing utilities using Rust-backed orjson with standard json fallback."""

import json
from typing import Any, Callable, Optional, Union

try:
    import orjson

    HAS_ORJSON = True
except ImportError:  # pragma: no cover
    orjson = None  # type: ignore[assignment]
    HAS_ORJSON = False

# orjson.JSONDecodeError inherits from json.JSONDecodeError (and ValueError)
JSONDecodeError = json.JSONDecodeError


def loads(data: Union[str, bytes]) -> Any:
    """Parse a JSON string or bytes into Python objects.

    Uses Rust-accelerated orjson when available (~5-10x faster),
    falling back to Python's standard library json module.
    """
    if HAS_ORJSON and orjson is not None:
        if isinstance(data, str):
            return orjson.loads(data.encode("utf-8"))
        return orjson.loads(data)
    if isinstance(data, bytes):
        return json.loads(data.decode("utf-8"))
    return json.loads(data)


def dumps(
    obj: Any,
    indent: bool = False,
    sort_keys: bool = False,
    default: Optional[Callable[[Any], Any]] = None,
) -> str:
    """Serialize a Python object into a JSON formatted string.

    Uses Rust-accelerated orjson when available,
    falling back to Python's standard library json module.
    """
    if HAS_ORJSON and orjson is not None:
        option = 0
        if indent:
            option |= orjson.OPT_INDENT_2
        if sort_keys:
            option |= orjson.OPT_SORT_KEYS
        encoded = orjson.dumps(obj, default=default, option=option)
        return encoded.decode("utf-8")
    return json.dumps(
        obj,
        indent=2 if indent else None,
        sort_keys=sort_keys,
        default=default or str,
    )


def dumps_bytes(
    obj: Any,
    indent: bool = False,
    sort_keys: bool = False,
    default: Optional[Callable[[Any], Any]] = None,
) -> bytes:
    """Serialize a Python object into JSON bytes."""
    if HAS_ORJSON and orjson is not None:
        option = 0
        if indent:
            option |= orjson.OPT_INDENT_2
        if sort_keys:
            option |= orjson.OPT_SORT_KEYS
        return orjson.dumps(obj, default=default, option=option)
    return dumps(obj, indent=indent, sort_keys=sort_keys, default=default).encode("utf-8")


def load_file(filepath: str) -> Any:
    """Read and parse a JSON file."""
    with open(filepath, "rb") as f:
        return loads(f.read())


def write_file(filepath: str, obj: Any, indent: bool = False) -> None:
    """Serialize and write an object to a JSON file."""
    with open(filepath, "wb") as f:
        f.write(dumps_bytes(obj, indent=indent))
