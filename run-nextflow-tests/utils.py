"""
Utility methods.
"""
import collections.abc
import itertools
import re
import json


ESCAPE_RE = re.compile(r"([^\\])\\([ =:])")
CLOSURE_RE = re.compile(r"^Script\S+_run_closure")


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


def parse_value(value_str: str):
    "Parse a value."
    # pylint: disable=too-many-branches
    try:
        if CLOSURE_RE.match(value_str):
            return "closure()"
    except TypeError:
        print(value_str)
        raise

    if value_str and value_str[0] == "[" and value_str[-1] == "]":
        value = []
        stack = []

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

    if value_str and value_str[0] == "{" and value_str[-1] == "}":
        value = {}
        for token in value_str[1:-1].split(", "):
            try:
                token_key, token_value = token.split("\\=", maxsplit=1)
            except ValueError:
                print(f"The bad value is `{value_str}`")
                print(f"The specific token is `{token}`")
                raise

            value[parse_value(token_key)] = parse_value(token_value)

        return value

    if value_str == "true":
        return True

    if value_str == "false":
        return False

    return ESCAPE_RE.sub(r"\1\2", value_str.strip())


def parse_config(config_str: str) -> dict:
    "Parse a string of Java properties."
    param_re = re.compile(r"^(?P<key>\S+?[^\\])=(?P<value>.*)$")

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

    config = {}

    for line in config_str.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            key, value = param_re.match(line).groups()
        except AttributeError:
            print(f"The offending line is `{line}`")
            raise

        assign_value(config, ESCAPE_RE.sub(r"\1\2", key), value)

    # Specifically sort the config
    return json.loads(json.dumps(config, sort_keys=True))
