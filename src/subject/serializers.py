from rest_framework import serializers

from subject.models import Subject, SubjectTimePreferenceState


class SubjectSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "weekly_hours",
            "duration",
            "preferred_time_slot",
            "time_preferences",
            "stage",
            "type",
            "teacher",
            "teacher_name",
            "group",
            "group_name",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "teacher_name",
            "group_name",
        ]

    def validate_duration(self, value):
        if value <= 0:
            raise serializers.ValidationError("Duration must be greater than zero.")
        return value

    def validate_weekly_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError("Weekly hours must be greater than zero.")
        return value

    def validate_time_preferences(self, value):
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("time_preferences must be an object.")

        valid_states = {state.value for state in SubjectTimePreferenceState}
        invalid_keys = []
        invalid_values = []

        for key, state in value.items():
            if not isinstance(key, str):
                invalid_keys.append(key)
                continue
            if state not in valid_states:
                invalid_values.append({"slot": key, "state": state})

        if invalid_keys:
            raise serializers.ValidationError(
                f"All time preference keys must be strings. Invalid keys: {invalid_keys}"
            )
        if invalid_values:
            raise serializers.ValidationError(
                {
                    "invalid_states": invalid_values,
                    "allowed": sorted(valid_states),
                }
            )

        return value
