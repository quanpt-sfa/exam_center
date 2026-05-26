"""Read-only SQL validation policy for minimal TEXTBOX_SQL execution.

This module intentionally implements an MVP tokenizer/validator and is not a
full SQL parser. It is designed to reduce risk for S2W-4.3 by allowing only
single-statement SELECT/WITH queries and blocking common mutating/admin verbs.
"""

from __future__ import annotations

import re
from typing import Any


_ALLOWED_FIRST_TOKENS = {"SELECT", "WITH"}
_FORBIDDEN_TOKENS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "CREATE",
    "ALTER",
    "DROP",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "COPY",
    "CALL",
    "DO",
    "EXECUTE",
    "VACUUM",
    "ANALYZE",
    "LOCK",
    "SET",
    "RESET",
}

_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _strip_sql_comments(sql: str) -> str:
    """Remove SQL line/block comments outside string literals.

    Block comments are removed entirely to make simple obfuscations like
    DR/**/OP detectable as DROP in downstream tokenization.
    """

    result: list[str] = []
    i = 0
    length = len(sql)
    in_single = False
    in_double = False

    while i < length:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < length else ""

        if in_single:
            result.append(ch)
            if ch == "'":
                if nxt == "'":
                    result.append(nxt)
                    i += 1
                else:
                    in_single = False
            i += 1
            continue

        if in_double:
            result.append(ch)
            if ch == '"':
                if nxt == '"':
                    result.append(nxt)
                    i += 1
                else:
                    in_double = False
            i += 1
            continue

        if ch == "'":
            in_single = True
            result.append(ch)
            i += 1
            continue

        if ch == '"':
            in_double = True
            result.append(ch)
            i += 1
            continue

        if ch == "-" and nxt == "-":
            i += 2
            while i < length and sql[i] not in "\r\n":
                i += 1
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < length and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def _remove_one_trailing_semicolon(sql: str) -> str:
    stripped = sql.rstrip()
    if stripped.endswith(";"):
        return stripped[:-1].rstrip()
    return stripped


def _contains_semicolon_outside_literals(sql: str) -> bool:
    in_single = False
    in_double = False

    for ch in sql:
        if in_single:
            if ch == "'":
                in_single = False
            continue
        if in_double:
            if ch == '"':
                in_double = False
            continue

        if ch == "'":
            in_single = True
            continue
        if ch == '"':
            in_double = True
            continue
        if ch == ";":
            return True

    return False


def _mask_string_literals(sql: str) -> str:
    """Replace literal contents with spaces to avoid false keyword matches."""

    result: list[str] = []
    i = 0
    length = len(sql)
    in_single = False
    in_double = False

    while i < length:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < length else ""

        if in_single:
            result.append(" ")
            if ch == "'":
                if nxt == "'":
                    result.append(" ")
                    i += 1
                else:
                    in_single = False
            i += 1
            continue

        if in_double:
            result.append(" ")
            if ch == '"':
                if nxt == '"':
                    result.append(" ")
                    i += 1
                else:
                    in_double = False
            i += 1
            continue

        if ch == "'":
            in_single = True
            result.append(" ")
            i += 1
            continue

        if ch == '"':
            in_double = True
            result.append(" ")
            i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def validate_read_only_sql(sql_text: str) -> dict[str, Any]:
    """Validate SQL text for minimal read-only execution policy.

    Limitations:
    - This validator uses token/pattern checks and is not a full SQL parser.
    - It may reject some valid edge-case SQL and should be hardened later.
    """

    if not isinstance(sql_text, str):
        return {
            "is_allowed": False,
            "normalized_sql": None,
            "reason_code": "invalid_sql_text_type",
            "message": "SQL text must be a string.",
        }

    stripped = sql_text.strip()
    if not stripped:
        return {
            "is_allowed": False,
            "normalized_sql": None,
            "reason_code": "empty_sql",
            "message": "SQL text is empty.",
        }

    without_comments = _strip_sql_comments(stripped).strip()
    normalized = _remove_one_trailing_semicolon(without_comments)

    if not normalized:
        return {
            "is_allowed": False,
            "normalized_sql": None,
            "reason_code": "empty_sql",
            "message": "SQL text is empty after comment removal.",
        }

    if _contains_semicolon_outside_literals(normalized):
        return {
            "is_allowed": False,
            "normalized_sql": None,
            "reason_code": "multiple_statements_not_allowed",
            "message": "Only one SQL statement is allowed.",
        }

    token_source = _mask_string_literals(normalized)
    tokens = [match.group(0).upper() for match in _IDENTIFIER_PATTERN.finditer(token_source)]

    if not tokens:
        return {
            "is_allowed": False,
            "normalized_sql": None,
            "reason_code": "empty_sql",
            "message": "No executable SQL tokens were found.",
        }

    first_token = tokens[0]
    if first_token not in _ALLOWED_FIRST_TOKENS:
        return {
            "is_allowed": False,
            "normalized_sql": None,
            "reason_code": "statement_type_not_allowed",
            "message": "Only SELECT and WITH statements are allowed.",
        }

    for token in tokens:
        if token in _FORBIDDEN_TOKENS:
            return {
                "is_allowed": False,
                "normalized_sql": None,
                "reason_code": "forbidden_keyword_detected",
                "message": f"Forbidden keyword detected by read-only policy: {token}.",
            }

    return {
        "is_allowed": True,
        "normalized_sql": normalized,
        "reason_code": None,
        "message": None,
    }
