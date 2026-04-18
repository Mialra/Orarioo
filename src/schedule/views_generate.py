"""Request parsing helpers for the schedule generation endpoint.

All functions parse and validate raw request payload values and return
either a parsed result or an error Response, following the (value, error)
tuple convention used throughout the codebase.
"""

from rest_framework import status
from rest_framework.response import Response


def parse_positive_int(raw_value, field_name):
    """Parse a raw value as a positive integer.
    Input: raw_value - raw query/body param value; field_name - name used in error messages
    Output: tuple (int, None) on success, or (None, Response) with HTTP 400 on failure
    """
    if raw_value in (None, ""):
        return None, None
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return None, Response(
            {"detail": f"{field_name} must be a positive integer."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if parsed <= 0:
        return None, Response(
            {"detail": f"{field_name} must be a positive integer."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return parsed, None


def parse_bool_param(raw_value, field_name):
    """Parse a raw value as a boolean accepting common string representations.
    Input: raw_value - raw query/body param; field_name - name used in error messages
    Output: tuple (bool, None) on success, or (False, Response) with HTTP 400 on invalid input;
            (False, None) when raw_value is None or empty
    """
    if raw_value in (None, ""):
        return False, None

    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True, None
    if normalized in {"0", "false", "no", "off"}:
        return False, None

    return False, Response(
        {
            "detail": (
                f"{field_name} must be a boolean value "
                "(true/false, 1/0, yes/no)."
            )
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def parse_generation_int(payload, field_name, *, min_value, max_value):
    """Parse and range-validate an integer generation option from the payload.
    Input: payload - request data dict; field_name - key to look up;
           min_value, max_value - inclusive bounds
    Output: tuple (int, None) on success, (None, None) if absent,
            or (None, Response) with HTTP 400 on validation failure
    """
    raw_value = payload.get(field_name)
    if raw_value in (None, ""):
        return None, None
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None, Response(
            {"detail": f"{field_name} must be an integer value."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if value < min_value or value > max_value:
        return None, Response(
            {
                "detail": (
                    f"{field_name} must be between {min_value} and {max_value}."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return value, None


def parse_generation_bool(payload, field_name):
    """Parse a boolean generation option from the payload.
    Input: payload - request data dict; field_name - key to look up
    Output: tuple (bool, None) on success, (None, None) if absent,
            or (None, Response) with HTTP 400 on invalid input
    """
    raw_value = payload.get(field_name)
    if raw_value in (None, ""):
        return None, None

    if isinstance(raw_value, bool):
        return raw_value, None

    return parse_bool_param(raw_value, field_name)


def parse_base_generation_bool_options(payload, options):
    """Parse boolean generation options (include_tc) from the payload into options dict.
    Input: payload - request data dict; options - mutable options dict to update
    Output: None on success, or Response with HTTP 400 on validation failure
    """
    for field_name in ["include_tc"]:
        parsed, error_response = parse_generation_bool(payload, field_name)
        if error_response is not None:
            return error_response
        if parsed is not None:
            options[field_name] = parsed
    return None


def parse_base_generation_int_options(payload, options):
    """Parse integer generation options (recess supervisors, tc_capacity) from the payload.
    Input: payload - request data dict; options - mutable options dict to update
    Output: None on success, or Response with HTTP 400 on validation failure
    """
    int_fields = {
        "recess_supervisors_preschool": (0, 20),
        "recess_supervisors_primary": (0, 20),
    }

    if options.get("include_tc", True):
        int_fields["tc_capacity"] = (1, 10)

    for field_name, bounds in int_fields.items():
        parsed, error_response = parse_generation_int(
            payload,
            field_name,
            min_value=bounds[0],
            max_value=bounds[1],
        )
        if error_response is not None:
            return error_response
        if parsed is not None:
            options[field_name] = parsed
    return None


DEFAULT_GENERATION_OPTIONS = {
    "recess_supervisors_preschool": 0,
    "recess_supervisors_primary": 0,
    "include_tc": True,
    "tc_capacity": 1,
}


def parse_generation_options(payload):
    """Parse and validate all generation options from the request payload.
    Input: payload - request data dict
    Output: tuple (options_dict, None) on success, or (None, Response) with HTTP 400 on failure
    """
    options = dict(DEFAULT_GENERATION_OPTIONS)
    bool_options_error = parse_base_generation_bool_options(payload, options)
    if bool_options_error is not None:
        return None, bool_options_error

    base_options_error = parse_base_generation_int_options(payload, options)
    if base_options_error is not None:
        return None, base_options_error

    return options, None
