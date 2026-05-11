"""Serializer for TCSession (Trabajo de Centro duty hours)."""

from rest_framework import serializers

from schedule.models import TCSession


class TCSessionSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    day_display = serializers.SerializerMethodField()
    duration_minutes = serializers.SerializerMethodField()

    class Meta:
        model = TCSession
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "day",
            "day_display",
            "start_time",
            "end_time",
            "duration_minutes",
            "name",
            "observations",
        ]

    def get_day_display(self, obj):
        return ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"][obj.day]

    def get_duration_minutes(self, obj):
        end = obj.end_time.hour * 60 + obj.end_time.minute
        start = obj.start_time.hour * 60 + obj.start_time.minute
        return end - start
