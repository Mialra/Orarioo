from __future__ import annotations

from copy import deepcopy

from rest_framework import status

NON_FIELD_ERRORS_KEY = "non_field_errors"


def build_error_entry(code, message, *, context=None):
    return {
        "code": str(code or "UNKNOWN_ERROR"),
        "message": str(message or ""),
        "context": deepcopy(context) if context else {},
    }


def build_field_errors(field_name, code, message, *, context=None):
    return {field_name: [build_error_entry(code, message, context=context)]}


def flatten_error_messages(errors):
    flattened = {}

    for field_name, entries in (errors or {}).items():
        normalized_entries = entries if isinstance(entries, list) else [entries]
        messages = []

        for entry in normalized_entries:
            if isinstance(entry, dict) and "message" in entry:
                messages.append(str(entry.get("message") or ""))
                continue
            messages.append(str(entry))

        flattened[field_name] = messages

    return flattened


class AppError(Exception):
    default_error_type = "application_error"
    default_status_code = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        code,
        message,
        *,
        context=None,
        status_code=None,
        error_type=None,
        errors=None,
        suggestions=None,
    ):
        super().__init__(message)
        self.code = str(code or "APPLICATION_ERROR")
        self.message = str(message or "")
        self.context = deepcopy(context) if context else {}
        self.status_code = (
            status_code if status_code is not None else self.default_status_code
        )
        self.error_type = error_type or self.default_error_type
        self.errors = deepcopy(errors) if errors else {}
        self.suggestions = list(suggestions or [])

    def structured_errors(self):
        if self.errors:
            return deepcopy(self.errors)
        return {
            NON_FIELD_ERRORS_KEY: [
                build_error_entry(self.code, self.message, context=self.context)
            ]
        }

    def to_response_data(self):
        errors = self.structured_errors()
        payload = flatten_error_messages(errors)
        payload["detail"] = self.message
        payload["errors"] = errors
        payload["_error"] = {
            "code": self.code,
            "type": self.error_type,
            "message": self.message,
            "context": deepcopy(self.context),
        }
        if self.suggestions:
            payload["suggestions"] = list(self.suggestions)
            payload["_error"]["suggestions"] = list(self.suggestions)
        payload["_meta"] = {
            "success": False,
            "status_code": self.status_code,
        }
        return payload


class ValidationAppError(AppError):
    default_error_type = "validation_error"
    default_status_code = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        code,
        message,
        *,
        field_name=None,
        context=None,
        errors=None,
        suggestions=None,
        status_code=None,
    ):
        structured_errors = errors
        if structured_errors is None and field_name:
            structured_errors = build_field_errors(
                field_name,
                code,
                message,
                context=context,
            )
        super().__init__(
            code,
            message,
            context=context,
            status_code=status_code or self.default_status_code,
            error_type=self.default_error_type,
            errors=structured_errors,
            suggestions=suggestions,
        )


class ResourceConflictError(AppError):
    default_error_type = "conflict_error"
    default_status_code = status.HTTP_409_CONFLICT


class NotFoundAppError(AppError):
    default_error_type = "not_found_error"
    default_status_code = status.HTTP_404_NOT_FOUND


class PermissionAppError(AppError):
    default_error_type = "permission_error"
    default_status_code = status.HTTP_403_FORBIDDEN


class ScheduleError(AppError):
    default_error_type = "schedule_error"
    default_status_code = status.HTTP_400_BAD_REQUEST


class ScheduleConflictError(ScheduleError):
    def __init__(
        self,
        *,
        teacher_name,
        subject_name,
        day,
        time_label,
        conflicting_subject,
        suggestions=None,
    ):
        message = (
            f"Cannot assign {subject_name} on {day} at {time_label} because "
            f"{teacher_name} is already assigned to {conflicting_subject}."
        )
        context = {
            "teacher": teacher_name,
            "subject": subject_name,
            "conflicting_subject": conflicting_subject,
            "day": day,
            "time": time_label,
        }
        super().__init__(
            "SCHEDULE_CONFLICT",
            message,
            context=context,
            suggestions=suggestions,
        )


class ScheduleCapacityError(ScheduleError):
    def __init__(
        self,
        *,
        resource_type,
        resource_name,
        assigned,
        capacity,
        suggestions=None,
    ):
        message = (
            f"{resource_type.title()} '{resource_name}' exceeds its available capacity: "
            f"{assigned} assigned, {capacity} available."
        )
        context = {
            "resource_type": resource_type,
            "resource_name": resource_name,
            "assigned": assigned,
            "capacity": capacity,
        }
        super().__init__(
            "SCHEDULE_CAPACITY_EXCEEDED",
            message,
            context=context,
            suggestions=suggestions,
        )


class ScheduleGenerationError(ScheduleError):
    def __init__(
        self,
        message="Unable to generate a schedule with the current constraints.",
        *,
        code="SCHEDULE_GENERATION_FAILED",
        context=None,
        suggestions=None,
        errors=None,
    ):
        super().__init__(
            code,
            message,
            context=context,
            errors=errors,
            suggestions=suggestions,
        )
