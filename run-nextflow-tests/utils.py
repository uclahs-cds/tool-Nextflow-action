"""
Utility methods.
"""
import collections.abc
import itertools
import json
import re
from typing import List, Any


CLOSURE_RE = re.compile(r"^Script\S+_run_closure")
DATE_RE = re.compile(r"\d{8}T\d{6}Z")
ESCAPE_RE = re.compile(r"([^\\])\\([ =:])")
POINTER_RE = re.compile(r"^(\[?Ljava\..*;@)(\w+)$")


def diff_json(alpha, beta):
    """
    Recursively generate differences.

    Differences are returned a list of (jsonpath, before, after) tuples.
    """
    # pylint: disable=too-many-branches
    results = []

    if alpha == beta:
        # They're the same - great!
        pass

    elif not isinstance(alpha, type(beta)):
        # Incomparable - bail out
        results.append(("", alpha, beta))

    elif isinstance(alpha, collections.abc.Mapping):
        for key, value in alpha.items():
            if key in beta:
                for sub_result in diff_json(value, beta[key]):
                    results.append((
                        f".{key}{sub_result[0]}",
                        sub_result[1],
                        sub_result[2]
                    ))
            else:
                results.append((key, value, None))

        for key, value in beta.items():
            if key not in alpha:
                results.append((key, None, value))

    elif isinstance(alpha, collections.abc.Sequence) and \
            not isinstance(alpha, str):

        for index, (alpha_val, beta_val) in \
                enumerate(itertools.zip_longest(alpha, beta)):
            for sub_result in diff_json(alpha_val, beta_val):
                results.append((
                    f"[{index}]{sub_result[0]}",
                    sub_result[1],
                    sub_result[2]
                ))

    else:
        # They're not collections and they are different
        results.append(("", alpha, beta))

    return results


def _parse_list_value(value_str: str) -> List[Any]:
    "Parse a list-like value."
    value = []
    stack = []

    assert value_str[0] == "["
    assert value_str[-1] == "]"

    list_str = value_str[1:-1]

    index = 0
    first_index = 0
    for index, character in enumerate(list_str):
        if character == "{":
            stack.append("}")
        elif character == "(":
            stack.append(")")
        elif character in ("}", ")"):
            assert stack[-1] == character
            stack.pop()

        elif character == "," and not stack:
            # Do not include the comma
            value.append(parse_value(list_str[first_index:index]))
            first_index = index + 1

    assert not stack

    if index > first_index:
        value.append(parse_value(list_str[first_index:]))

    return value


def _parse_dict_value(value_str: str) -> dict:
    "Parse a dictionary-like value."
    value = {}

    assert value_str[0] == "{"
    assert value_str[-1] == "}"

    for token in value_str[1:-1].split(", "):
        try:
            token_key, token_value = token.split("\\=", maxsplit=1)
        except ValueError:
            print(f"The bad value is `{value_str}`")
            print(f"The specific token is `{token}`")
            raise

        value[parse_value(token_key)] = parse_value(token_value)

    return value


def parse_value(value_str: str) -> Any:
    "Parse a value."
    try:
        if CLOSURE_RE.match(value_str):
            return "closure()"
    except TypeError:
        print(value_str)
        raise

    value: Any = None

    # Mask any memory addresses
    if POINTER_RE.match(value_str):
        value = POINTER_RE.sub(r"\1dec0ded", value_str)

    elif value_str and value_str[0] == "[" and value_str[-1] == "]":
        value = _parse_list_value(value_str)

    elif value_str and value_str[0] == "{" and value_str[-1] == "}":
        value = _parse_dict_value(value_str)

    elif value_str == "true":
        value = True

    elif value_str == "false":
        value = False

    else:
        value = ESCAPE_RE.sub(r"\1\2", value_str.strip())

    return value


def parse_config(config_str: str,
                 dated_fields: List[str],
                 version_fields: List[str]) -> dict:
    "Parse a string of Java properties."
    param_re = re.compile(r"^(?P<key>\S+?[^\\])=(?P<value>.*)$")
    version_fields = version_fields[:]

    def assign_value(closure, key, value):
        if "." not in key:
            # This needs to be def'd
            if key != "json_object":
                closure[key] = parse_value(value)
        else:
            local_key, remainder = key.split(".", maxsplit=1)

            if local_key not in closure:
                closure[local_key] = {}

            assign_value(closure[local_key], remainder, value)

    # Parse out the current manifest version
    try:
        version_str = re.search(
            r"^manifest.version=(.*)$",
            config_str,
            re.MULTILINE
        ).group(1)

        # Add 'manifest.version' to the list of fields to be masked
        version_fields.append("manifest.version")

    except AttributeError:
        version_str = None

    config: dict[str, Any] = {}

    for line in config_str.splitlines():
        line = line.strip()
        if not line:
            continue

        param_match = param_re.match(line)
        if not param_match:
            raise ValueError(f"The offending line is `{line}`")

        key, value = param_match.groups()

        escaped_key = ESCAPE_RE.sub(r"\1\2", key)
        if escaped_key in dated_fields:
            # Replace the date with Pathfinder's landing
            value = DATE_RE.sub("19970704T165655Z", value)

        if escaped_key in version_fields and version_str:
            # Replace the version with an obvious weird value
            value = value.replace(version_str, "VER.SI.ON")

        assign_value(config, escaped_key, value)

    # Specifically sort the config
    return json.loads(json.dumps(config, sort_keys=True))
