"""
Shared serializer helpers: audit field name constants and a field list builder.
"""

AUDIT_FIELD_NAMES = (
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
)

AUDIT_READ_ONLY_FIELD_NAMES = ("id", *AUDIT_FIELD_NAMES)


def with_audit_fields(*fields):
    """Build a serializer fields list that prepends 'id' and appends all four audit fields.
    Input: *fields - arbitrary field names to include between id and the audit fields
    Output: list starting with 'id', then the given fields, then the four audit fields
    """
    return ["id", *fields, *AUDIT_FIELD_NAMES]
