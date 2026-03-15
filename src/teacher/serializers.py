from rest_framework import serializers

from teacher.models import Teacher, TeacherTimePreferenceState


class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = [
            "id",
            "name",
            "max_weekly_hours",
            "working_hours",
            "preferences",
            "time_preferences",
            "availability",
            "unavailability",
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
        ]

    def validate(self, attrs):
        max_weekly_hours = attrs.get(
            "max_weekly_hours",
            self.instance.max_weekly_hours if self.instance else None,
        )
        working_hours = attrs.get(
            "working_hours",
            self.instance.working_hours if self.instance else 0,
        )

        if max_weekly_hours is not None and working_hours > max_weekly_hours:
            raise serializers.ValidationError(
                {
                    "working_hours": (
                        "working_hours cannot be greater than max_weekly_hours."
                    )
                }
            )

        time_preferences = attrs.get(
            "time_preferences",
            self.instance.time_preferences if self.instance else {},
        )
        if time_preferences in (None, ""):
            attrs["time_preferences"] = {}
            return attrs

        if not isinstance(time_preferences, dict):
            raise serializers.ValidationError(
                {"time_preferences": "time_preferences must be an object."}
            )

        valid_states = {state.value for state in TeacherTimePreferenceState}
        invalid_values = [
            {"slot": key, "state": state}
            for key, state in time_preferences.items()
            if not isinstance(key, str) or state not in valid_states
        ]

        if invalid_values:
            raise serializers.ValidationError(
                {
                    "time_preferences": {
                        "invalid_states": invalid_values,
                        "allowed": sorted(valid_states),
                    }
                }
            )

        return attrs
