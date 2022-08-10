"""This module contains functions which return lists of names of known library functions that may be
interesting for security or dataflow."""

from typing import List

_sql_keywords: List[str] = ["ALTER", "SELECT", "TABLE", "CREATE", "DELETE", "DROP", "INSERT"]

_http_keywords: List[str] = ["url", "POST", "GET", "REQUEST", "http", "https"]

_os_commands: List[str] = ["find ", "exec ", "source ", "ssh "]

_string_output_func_names: List[str] = [
    "fprintf",
    "printf",
    "snprintf",
    "sprintf",
    "dprintf",
    "vfprintf",
    "vprintf",
    "vdprintf",
    "vsprintf",
    "vsnprintf",
    "vsscanf",
    "asprintf",
    "wprintf",
    "fwprintf",
    "swprintf",
    "vwprintf",
    "vfwprintf",
    "vswprintf",
    "snprintf",
    "fputs",
    "puts",
    "write",
    "fwrite",
    "fputws",
]


def formatted_output_function_names() -> List[str]:
    """Returns the names of functions like printf which format and print strings."""
    return _string_output_func_names


def protocol_keywords() -> List[str]:
    """Returns keywords of known protocols like SQL and HTTP."""
    return _sql_keywords + _http_keywords


def sql_keywords() -> List[str]:
    """Returns SQL keywords."""
    return _sql_keywords + [keyword.lower() for keyword in _sql_keywords]
