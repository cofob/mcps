from typing import TypeGuard

from mcp_common.types import JsonArray, JsonObject, JsonValue


def is_json_object(value: JsonValue) -> TypeGuard[JsonObject]:
    return isinstance(value, dict)


def is_json_array(value: JsonValue) -> TypeGuard[JsonArray]:
    return isinstance(value, list)


def is_json_string(value: JsonValue) -> TypeGuard[str]:
    return isinstance(value, str)


def is_json_int(value: JsonValue) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def is_json_bool(value: JsonValue) -> TypeGuard[bool]:
    return isinstance(value, bool)


def expect_object(value: JsonValue, *, context: str) -> JsonObject:
    if is_json_object(value):
        return value
    raise ValueError(f"Expected JSON object for {context}.")


def expect_array(value: JsonValue, *, context: str) -> JsonArray:
    if is_json_array(value):
        return value
    raise ValueError(f"Expected JSON array for {context}.")


def get_object(mapping: JsonObject, key: str, *, context: str) -> JsonObject:
    value = mapping.get(key)
    if value is None:
        return {}
    return expect_object(value, context=f"{context}.{key}")


def get_object_list(mapping: JsonObject, key: str, *, context: str) -> list[JsonObject]:
    value = mapping.get(key)
    if value is None:
        return []
    items = expect_array(value, context=f"{context}.{key}")
    return [expect_object(item, context=f"{context}.{key}[]") for item in items]


def get_str(mapping: JsonObject, key: str) -> str | None:
    value = mapping.get(key)
    if value is not None and is_json_string(value):
        return value
    return None


def get_int(mapping: JsonObject, key: str) -> int | None:
    value = mapping.get(key)
    if value is not None and is_json_int(value):
        return value
    return None


def get_bool(mapping: JsonObject, key: str) -> bool | None:
    value = mapping.get(key)
    if value is not None and is_json_bool(value):
        return value
    return None
