from collections.abc import Mapping, Sequence

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | JsonArray | JsonObject
type JsonArray = list[JsonValue]
type JsonObject = dict[str, JsonValue]

type HttpQueryScalar = str | int | float | bool | None
type HttpQuerySequence = Sequence[HttpQueryScalar]
type HttpQueryParams = Mapping[str, HttpQueryScalar | HttpQuerySequence]
