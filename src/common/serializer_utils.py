AUDIT_FIELD_NAMES = (
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
)

AUDIT_READ_ONLY_FIELD_NAMES = ("id", *AUDIT_FIELD_NAMES)


def with_audit_fields(*fields):
    return ["id", *fields, *AUDIT_FIELD_NAMES]
