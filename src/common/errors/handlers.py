from __future__ import annotations

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from common.errors.exceptions import (
    NON_FIELD_ERRORS_KEY,
    AppError,
    build_error_entry,
    flatten_error_messages,
)

logger = logging.getLogger(__name__)

CONTROL_KEYS = {"detail", "_error", "_meta", "errors", "suggestions"}


def _normalize_error_details(value):
    if isinstance(value, ErrorDetail):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize_error_details(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_error_details(item) for item in value]
    return value


def _extract_message(value, fallback):
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, str) and message.strip():
            return message
        detail = value.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail
        for nested in value.values():
            extracted = _extract_message(nested, "")
            if extracted:
                return extracted
        return fallback

    if isinstance(value, list):
        for item in value:
            extracted = _extract_message(item, "")
            if extracted:
                return extracted
        return fallback

    if isinstance(value, str) and value.strip():
        return value

    return fallback


def _payload_to_structured_entries(raw_value, *, default_code, field_name=None):
    if isinstance(raw_value, list):
        entries = []
        for item in raw_value:
            entries.extend(
                _payload_to_structured_entries(
                    item,
                    default_code=default_code,
                    field_name=field_name,
                )
            )
        return entries

    if isinstance(raw_value, dict):
        has_explicit_shape = "message" in raw_value or "code" in raw_value
        if has_explicit_shape:
            return [
                build_error_entry(
                    raw_value.get("code") or default_code,
                    raw_value.get("message")
                    or _extract_message(
                        raw_value, "The request could not be processed."
                    ),
                    context=raw_value.get("context") or {},
                )
            ]

        return [
            build_error_entry(
                default_code,
                _extract_message(raw_value, "The request could not be processed."),
                context={"field": field_name} if field_name else {},
            )
        ]

    if raw_value in (None, ""):
        return []

    return [
        build_error_entry(
            default_code,
            str(raw_value),
            context={"field": field_name} if field_name else {},
        )
    ]


def _extract_error_code(exc, status_code):
    if isinstance(exc, AppError):
        return exc.code

    default_code = getattr(exc, "default_code", None)
    if isinstance(default_code, str) and default_code:
        return default_code.upper()

    status_to_code = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_409_CONFLICT: "CONFLICT",
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "UNSUPPORTED_MEDIA_TYPE",
        status.HTTP_429_TOO_MANY_REQUESTS: "THROTTLED",
    }
    return status_to_code.get(status_code, "API_ERROR")


def _build_structured_errors(payload, *, default_code):
    if isinstance(payload, dict):
        explicit_errors = payload.get("errors")
        if isinstance(explicit_errors, dict):
            return {
                field_name: _payload_to_structured_entries(
                    value,
                    default_code=default_code,
                    field_name=field_name,
                )
                for field_name, value in explicit_errors.items()
            }

        field_entries = {}
        for key, value in payload.items():
            if key in CONTROL_KEYS:
                continue
            field_entries[key] = _payload_to_structured_entries(
                value,
                default_code=default_code,
                field_name=key,
            )

        populated_fields = {
            field_name: entries
            for field_name, entries in field_entries.items()
            if entries
        }
        if populated_fields:
            return populated_fields

        detail = payload.get("detail")
        return {
            NON_FIELD_ERRORS_KEY: _payload_to_structured_entries(
                detail or payload,
                default_code=default_code,
            )
        }

    return {
        NON_FIELD_ERRORS_KEY: _payload_to_structured_entries(
            payload,
            default_code=default_code,
        )
    }


def _extract_detail_message(payload, *, structured_errors, fallback):
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail

    flattened = flatten_error_messages(structured_errors)
    for messages in flattened.values():
        if isinstance(messages, list) and messages:
            first = str(messages[0] or "").strip()
            if first:
                return first

    return fallback


def _build_internal_error_response():
    message = "An internal server error occurred."
    payload = {
        "detail": message,
        "errors": {
            NON_FIELD_ERRORS_KEY: [
                build_error_entry(
                    "INTERNAL_ERROR",
                    message,
                )
            ]
        },
    }
    payload.update(flatten_error_messages(payload["errors"]))
    payload["_error"] = {
        "code": "INTERNAL_ERROR",
        "type": "server_error",
        "message": message,
        "context": {},
    }
    payload["_meta"] = {
        "success": False,
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }
    return Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def api_exception_handler(exc, context):
    if isinstance(exc, AppError):
        return Response(exc.to_response_data(), status=exc.status_code)

    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            exc = ValidationError(exc.message_dict)
        else:
            exc = ValidationError(exc.messages)

    response = drf_exception_handler(exc, context)

    if response is None:
        logger.exception(
            "Unhandled backend exception type=%s",
            exc.__class__.__name__,
        )
        return _build_internal_error_response()

    if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Server-side API exception type=%s",
            exc.__class__.__name__,
        )
        return _build_internal_error_response()

    normalized_payload = _normalize_error_details(response.data)
    default_code = _extract_error_code(exc, response.status_code)
    structured_errors = _build_structured_errors(
        normalized_payload,
        default_code=default_code,
    )
    detail_message = _extract_detail_message(
        normalized_payload,
        structured_errors=structured_errors,
        fallback="The request could not be processed.",
    )

    legacy_payload = flatten_error_messages(structured_errors)
    legacy_payload["detail"] = detail_message
    legacy_payload["errors"] = structured_errors

    if isinstance(normalized_payload, dict) and normalized_payload.get("suggestions"):
        legacy_payload["suggestions"] = normalized_payload["suggestions"]

    legacy_payload["_error"] = {
        "code": default_code,
        "type": "validation_error" if response.status_code < 500 else "server_error",
        "message": detail_message,
        "context": {},
    }
    legacy_payload["_meta"] = {
        "success": False,
        "status_code": response.status_code,
    }

    response.data = legacy_payload
    return response
