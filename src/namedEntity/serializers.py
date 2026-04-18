"""
Serializer mixin for name validation shared by all NamedEntity-backed serializers.
"""

from app.constants import STRING_MAX_LENGTH
from common.validators import (
    validate_and_normalize_required_text,
    validate_case_insensitive_unique,
)


class NamedEntityNameValidationMixin:
    """Reusable `name` normalization for serializers bound to NamedEntity models."""

    name_max_length = STRING_MAX_LENGTH
    enforce_case_insensitive_unique_name = False

    def _get_model_class(self):
        """Resolve the model class from the serializer Meta inner class.
        Input: self - serializer instance expected to have a Meta.model attribute
        Output: model class if found, or None
        """
        return getattr(getattr(self, "Meta", None), "model", None)

    def validate_name(self, value):
        """Normalize and optionally enforce case-insensitive uniqueness on the name field.
        Input: value - raw name string from the request
        Output: normalized name string; raises ValidationError on blank, length, or duplicate
        """
        normalized = validate_and_normalize_required_text(
            value,
            field_name="name",
            label="name",
            max_length=self.name_max_length,
        )

        if not self.enforce_case_insensitive_unique_name:
            return normalized

        model = self._get_model_class()
        if model is None:
            return normalized

        return validate_case_insensitive_unique(
            normalized,
            field_name="name",
            queryset=model.objects.all(),
            instance=getattr(self, "instance", None),
            label="name",
        )
