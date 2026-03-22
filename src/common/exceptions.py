import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def _normalize_error_details(value):
    if isinstance(value, ErrorDetail):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize_error_details(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_error_details(item) for item in value]
    return value


def _extract_detail_message(payload, fallback):
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail

        for key, value in payload.items():
            if key in {"detail", "_error", "_meta", "errors"}:
                continue
            if isinstance(value, list) and value:
                first = value[0]
                if isinstance(first, str) and first.strip():
                    return first
            if isinstance(value, str) and value.strip():
                return value

    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, str) and first.strip():
            return first

    return fallback


def _extract_error_code(exc, status_code):
    default_code = getattr(exc, "default_code", None)
    if isinstance(default_code, str) and default_code:
        return default_code

    status_to_code = {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
        status.HTTP_429_TOO_MANY_REQUESTS: "throttled",
    }
    return status_to_code.get(status_code, "api_error")


def _build_errors_block(payload):
    if isinstance(payload, dict):
        field_errors = {
            key: value
            for key, value in payload.items()
            if key not in {"detail", "_error", "_meta", "errors"}
        }
        if field_errors:
            return field_errors
        if "detail" in payload:
            return {"non_field_errors": [payload["detail"]]}
        return {}

    if isinstance(payload, list):
        return {"non_field_errors": payload}

    return {"non_field_errors": [str(payload)]}


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            exc = ValidationError(exc.message_dict)
        else:
            exc = ValidationError(exc.messages)

    response = drf_exception_handler(exc, context)

    if response is not None and response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.exception("Server-side API exception", exc_info=exc)
        return Response(
            {
                "detail": "An internal server error occurred.",
                "errors": {"non_field_errors": ["An internal server error occurred."]},
                "_error": {
                    "code": "internal_error",
                    "type": "server_error",
                    "message": "An internal server error occurred.",
                },
                "_meta": {
                    "success": False,
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if response is None:
        logger.exception("Unhandled backend exception", exc_info=exc)
        return Response(
            {
                "detail": "An internal server error occurred.",
                "errors": {"non_field_errors": ["An internal server error occurred."]},
                "_error": {
                    "code": "internal_error",
                    "type": "server_error",
                    "message": "An internal server error occurred.",
                },
                "_meta": {
                    "success": False,
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    normalized_payload = _normalize_error_details(response.data)
    detail_message = _extract_detail_message(
        normalized_payload,
        fallback="The request could not be processed.",
    )

    if not isinstance(normalized_payload, dict):
        normalized_payload = {
            "detail": detail_message,
            "errors": _build_errors_block(normalized_payload),
        }
    else:
        normalized_payload.setdefault("detail", detail_message)
        normalized_payload.setdefault("errors", _build_errors_block(normalized_payload))

    normalized_payload["_error"] = {
        "code": _extract_error_code(exc, response.status_code),
        "type": "validation_error" if response.status_code < 500 else "server_error",
        "message": detail_message,
    }
    normalized_payload["_meta"] = {
        "success": False,
        "status_code": response.status_code,
    }

    response.data = normalized_payload
    return response
