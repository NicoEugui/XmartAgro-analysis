"""A small checker of the subset of JSON Schema the frontend schema uses (no dependency), plus a walk over its descriptions."""


def _type_ok(kind, value):
    return {"string": isinstance(value, str), "boolean": isinstance(value, bool), "null": value is None,
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "object": isinstance(value, dict), "array": isinstance(value, list)}[kind]


def problems(value, schema, root, path="$"):
    """Every way `value` does not satisfy `schema` (empty list if it does)."""
    if "$ref" in schema:
        return problems(value, root["$defs"][schema["$ref"].rsplit("/", 1)[1]], root, path)
    if "anyOf" in schema:
        options = [problems(value, option, root, path) for option in schema["anyOf"]]
        return [] if any(not o for o in options) else [f"{path}: matches none of the alternatives"]
    out = []
    if "type" in schema and not _type_ok(schema["type"], value):
        return [f"{path}: expected {schema['type']}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if "const" in schema and value != schema["const"]:
        out.append(f"{path}: expected {schema['const']!r}")
    if schema.get("type") == "object":
        props = schema.get("properties", {})
        out += [f"{path}: missing {k}" for k in schema.get("required", []) if k not in value]
        for key, item in value.items():
            if key in props:
                out += problems(item, props[key], root, f"{path}.{key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                out += problems(item, schema["additionalProperties"], root, f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                out.append(f"{path}: unexpected field {key}")
    if schema.get("type") == "array":
        for index, item in enumerate(value):
            out += problems(item, schema["items"], root, f"{path}[{index}]")
    return out


def missing(schema, key, path="$"):
    """Schema nodes without `key` (e.g. description or x-used-in): a property, an array item or a definition."""
    out = []
    if ("type" in schema or "$ref" in schema or "anyOf" in schema) and not schema.get(key):
        out.append(path)
    for section in ("properties", "$defs"):
        for name, sub in schema.get(section, {}).items():
            out += missing(sub, key, f"{path}.{name}")
    for section in ("items", "additionalProperties"):
        if isinstance(schema.get(section), dict):
            out += missing(schema[section], key, f"{path}.{section}")
    return out
