from rest_framework import serializers

from auditableEntity.audit import ENTITY_LABELS
from auditableEntity.models import AuditEntry


class AuditEntrySerializer(serializers.ModelSerializer):
    tipo_entidad = serializers.SerializerMethodField()
    nombre_entidad = serializers.CharField(source="entity_name", read_only=True)
    tipo_accion = serializers.SerializerMethodField()
    detalle = serializers.CharField(source="detail", read_only=True)
    cambios = serializers.JSONField(source="changed_fields", read_only=True)
    usuario = serializers.CharField(source="actor_name", read_only=True)
    fecha = serializers.DateTimeField(source="occurred_at", read_only=True)

    class Meta:
        model = AuditEntry
        fields = [
            "tipo_entidad",
            "nombre_entidad",
            "tipo_accion",
            "detalle",
            "cambios",
            "usuario",
            "fecha",
        ]
        read_only_fields = fields

    def get_tipo_entidad(self, obj):
        return ENTITY_LABELS.get(obj.entity_type, obj.entity_type)

    def get_tipo_accion(self, obj):
        mapping = {
            "CREATE": "Creación",
            "UPDATE": "Modificación",
            "DELETE": "Borrado",
        }
        return mapping.get(obj.action_type, obj.action_type)
