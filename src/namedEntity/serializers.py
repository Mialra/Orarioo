from rest_framework import serializers

from common.validation import validate_and_normalize_required_text


class NamedEntityNameValidationMixin:
    """Reusable `name` normalization for serializers bound to NamedEntity models."""

    name_max_length = 150
    enforce_case_insensitive_unique_name = False

    def validate_name(self, value):
        normalized = validate_and_normalize_required_text(
            value,
            field_name="name",
            max_length=self.name_max_length,
        )

        if not self.enforce_case_insensitive_unique_name:
            return normalized

        model = getattr(getattr(self, "Meta", None), "model", None)
        if model is None:
            return normalized

        queryset = model.objects.filter(name__iexact=normalized)
        instance = getattr(self, "instance", None)
        if instance is not None and getattr(instance, "pk", None) is not None:
            queryset = queryset.exclude(pk=instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "An entity with this name already exists (case-insensitive)."
            )

        return normalized
