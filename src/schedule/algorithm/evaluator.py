from typing import List, Dict, Any
from django.utils import timezone
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# Franjas horarias por etapa educativa (excluye descansos)
# IMPORTANTE: 'end' es la ÚLTIMA HORA DE CLASE, no la hora de fin del horario
# Ej: Si es 9:00-14:00, la última clase es 13:00-14:00 (hora 13), no hora 14
STAGE_HOURS = {
    'preschool': {
        'name': 'Infantil',
        'start': 9,        # Primera clase 9:00
        'end': 13,         # Última clase 13:00-14:00
        'break': (10.5, 11),  # 10:30-11:00
    },
    'primary': {
        'name': 'Primaria',
        'start': 9,        # Primera clase 9:00
        'end': 13,         # Última clase 13:00-14:00
        'break': (11.5, 12),  # 11:30-12:00
    },
    'secondary': {
        'name': 'ESO',
        'start': 8,        # Primera clase 8:00
        'end': 13,         # Última clase 13:30-14:30 (tomamos hora 13)
        'break': (11, 11.5),  # 11:00-11:30
    },
}


class ScheduleEvaluator:
    """
    Analiza horarios generados para detectar defectos no-críticos.
    Ejecuta DESPUÉS de la generación, no falla el proceso.
    """

    @staticmethod
    def get_expected_hours_for_stage(stage):
        """
        Retorna las horas esperadas para una etapa, excluyendo descansos.

        Args:
            stage: 'preschool', 'primary', 'secondary'

        Returns:
            set de horas esperadas
        """
        config = STAGE_HOURS.get(stage)
        if not config:
            # Default si no se reconoce etapa
            config = STAGE_HOURS['primary']

        start = int(config['start'])
        end = int(config['end'])
        break_start = config['break'][0]
        break_end = config['break'][1]

        # Crear set de horas, excluyendo el descanso
        expected = set()
        for hour in range(start, end + 1):
            # Excluir descanso
            if break_start <= hour < break_end:
                continue
            expected.add(hour)

        return expected

    @staticmethod
    def analyze_gaps_groups(schedules):
        """
        Detecta huecos internos (gaps) dentro de cada grupo y día.

        Detecta dos tipos de gaps:
        1. Internos: Entre sesiones (ej: 9:00 → 11:00, falta 10:00)
        2. Estructurales: Fuera del rango esperado para la etapa

        Args:
            schedules: Queryset o lista de Schedule objects

        Returns:
            Lista de defectos por gaps detectados
        """
        logger.info(f"analyze_gaps_groups: Analizando {len(schedules)} schedules")

        defects = []

        # Agrupar sesiones por grupo y día
        sessions_by_group_day = defaultdict(lambda: {
            'group': None,
            'group_name': '',
            'date': '',
            'hours': set(),
            'stage': None,
        })

        processed = 0
        skipped = 0

        for schedule in schedules:
            if not schedule.group or not schedule.start_time:
                skipped += 1
                continue

            processed += 1

            # Convertir a hora local y extraer fecha y hora
            local_start = timezone.localtime(schedule.start_time)
            date_key = local_start.strftime('%Y-%m-%d')
            hour = local_start.hour

            # Clave para agrupar: grupo_id + fecha
            group_day_key = f"{schedule.group.id}_{date_key}"

            sessions_by_group_day[group_day_key]['group'] = schedule.group
            sessions_by_group_day[group_day_key]['group_name'] = schedule.group.name
            sessions_by_group_day[group_day_key]['date'] = date_key
            sessions_by_group_day[group_day_key]['hours'].add(hour)

            # Obtener stage del grupo de forma segura
            try:
                stage = schedule.group.stage if hasattr(schedule.group, 'stage') else 'primary'
            except Exception as e:
                logger.debug(f"Error getting stage: {e}")
                stage = 'primary'
            sessions_by_group_day[group_day_key]['stage'] = stage

        logger.info(f"Processed: {processed}, Skipped: {skipped}, Group-day combinations: {len(sessions_by_group_day)}")

        # Detectar gaps internos Y estructurales
        for group_day_key, day_data in sessions_by_group_day.items():
            if not day_data['hours']:
                continue

            stage = day_data['stage'] or 'primary'
            expected_hours = ScheduleEvaluator.get_expected_hours_for_stage(stage)
            stage_config = STAGE_HOURS.get(stage, STAGE_HOURS['primary'])

            hours_set = day_data['hours']
            hours_list = sorted(hours_set)

            # TIPO 1: Detectar GAPS INTERNOS (entre sesiones consecutivas)
            for i in range(len(hours_list) - 1):
                current_hour = hours_list[i]
                next_hour = hours_list[i + 1]

                # Si hay más de 1 hora de diferencia, hay un gap
                if next_hour - current_hour > 1:
                    for missing_hour in range(current_hour + 1, next_hour):
                        # No reportar descansos como gaps
                        if missing_hour in expected_hours:
                            defect = {
                                'entity_id': day_data['group'].id,
                                'entity_name': day_data['group_name'],
                                'entity_type': 'group',
                                'severity': 'MEDIUM',
                                'gap_type': 'INTERNAL',
                                'description': (
                                    f"{day_data['group_name']} - {day_data['date']} "
                                    f"{str(missing_hour).zfill(2)}:00: Hueco detectado"
                                ),
                                'context': {
                                    'date': day_data['date'],
                                    'hour': missing_hour,
                                    'hours_occupied': hours_list,
                                    'stage': stage,
                                }
                            }
                            defects.append(defect)
                            logger.info(f"DEFECT INTERNAL: {defect['description']}")

            # TIPO 2: Detectar GAPS ESTRUCTURALES (horas faltantes en la franja esperada)
            missing_expected_hours = expected_hours - hours_set

            if missing_expected_hours:
                for missing_hour in sorted(missing_expected_hours):
                    defect = {
                        'entity_id': day_data['group'].id,
                        'entity_name': day_data['group_name'],
                        'entity_type': 'group',
                        'severity': 'LOW',
                        'gap_type': 'BOUNDARY',
                        'description': (
                            f"{day_data['group_name']} - {day_data['date']} "
                            f"{str(missing_hour).zfill(2)}:00: Sesión faltante"
                        ),
                        'context': {
                            'date': day_data['date'],
                            'hour': missing_hour,
                            'hours_occupied': hours_list,
                            'expected_range': f"{int(stage_config['start'])}:00 - {stage_config['end']}:00",
                            'stage': stage,
                        }
                    }
                    defects.append(defect)
                    logger.info(f"DEFECT BOUNDARY: {defect['description']}")

        logger.info(f"analyze_gaps_groups: Detectados {len(defects)} gaps")
        return defects

    @staticmethod
    def analyze_schedules(schedules):
        """
        Función principal que orquesta el análisis de horarios.
        Llama a subfunciones especializadas para detectar diferentes tipos de defectos.

        Args:
            schedules: Queryset o lista de Schedule objects

        Returns:
            Lista consolidada de defectos encontrados
        """
        logger.info(f"=== analyze_schedules START - Total schedules: {len(schedules) if schedules else 0} ===")

        if not schedules:
            logger.warning("No schedules provided")
            return []

        all_defects = []

        # Ejecutar análisis especializados
        gaps_defects = ScheduleEvaluator.analyze_gaps_groups(schedules)
        all_defects.extend(gaps_defects)

        logger.info(f"=== analyze_schedules END - Total defects: {len(all_defects)} ===")
        return all_defects
