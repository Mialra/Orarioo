from app.constants import STRING_MAX_LENGTH
from common.validators.validators import (
    validate_and_normalize_required_text,
    validate_case_insensitive_unique,
)


class NamedEntityNameValidationMixin:
    """Reusable `name` normalization for serializers bound to NamedEntity models."""

    name_max_length = STRING_MAX_LENGTH
    enforce_case_insensitive_unique_name = False

    def validate_name(self, value):
        normalized = validate_and_normalize_required_text(
            value,
            field_name="name",
            label="name",
            max_length=self.name_max_length,
        )

        if not self.enforce_case_insensitive_unique_name:
            return normalized

        model = getattr(getattr(self, "Meta", None), "model", None)
        if model is None:
            return normalized

        return validate_case_insensitive_unique(
            normalized,
            field_name="name",
            queryset=model.objects.all(),
            instance=getattr(self, "instance", None),
            label="name",
        )
