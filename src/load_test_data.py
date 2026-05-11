"""
Script to load test data into all entities for easy testing.
Run from the src directory with: python load_test_data.py

Dataset target:
- 1º, 2º, 3º de Infantil
- 1º a 6º de Primaria
- 1º a 4º de ESO
- One group per year (no A/B split)

Soft-constraint coverage designed into this dataset:
- Teacher preferences: mañaneros fuertes, tardes fuertes, sin prefs, mix PREFER_YES/PREFER_NO
- Subject preferences: cognitivas de mañana, EF/Música de mediodía, tarde para arte
- Gap minimization: Rubén (EF) enseña 13 grupos con unavailabilities → candidatos a huecos
- Subject day spread: Lengua y Matemáticas con 5-6 sesiones/semana
- TC distribution: 13 grupos con tutoría repartida entre tutores y orientación
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

# NOTE: These imports must come after django.setup() - ignore E402
from django.contrib.auth import get_user_model  # noqa: E402

from auditableEntity.audit import AUDITABLE_ENTITY_TYPES  # noqa: E402
from auditableEntity.audit import suppress_audit_events  # noqa: E402
from auditableEntity.models import AuditActionType, AuditEntry  # noqa: E402
from classroom.models import Classroom  # noqa: E402
from group.models import EducationalStage as GroupEducationalStage  # noqa: E402
from group.models import Group  # noqa: E402
from schedule.algorithm.slots import build_weekly_slots  # noqa: E402
from schedule.algorithm.slots import session_stage_code  # noqa: E402
from schedule.constants import SAVED_TIMETABLE_PREFIX  # noqa: E402
from schedule.models import Schedule  # noqa: E402
from subject.models import EducationalStage  # noqa: E402
from subject.models import Subject  # noqa: E402
from subject.models import SubjectTimePreferenceState  # noqa: E402
from subject.models import SubjectType  # noqa: E402; noqa: E402
from teacher.models import Teacher, TeacherTimePreferenceState  # noqa: E402
from user.models import CollaborationTeam  # noqa: E402

User = get_user_model()

DAY_CODES = ["MON", "TUE", "WED", "THU", "FRI"]

# Slot start times matching STAGE_SLOT_WINDOWS in slots.py (non-recess slots only).
# Preference keys are built as "DAY_HH:MM", e.g. "MON_09:00".
#   PRESCHOOL  → 09:00-14:00, breaks 10:30-11:00 and 13:30-14:00
#   PRIMARY    → 09:00-14:00, break 11:30-12:00
#   SECONDARY  → 08:00-14:30, break 11:00-11:30
PRESCHOOL_SLOT_TIMES = ["09:00", "10:00", "11:00", "12:00", "13:00"]
PRIMARY_SLOT_TIMES = ["09:00", "10:00", "11:00", "12:00", "13:00"]
SECONDARY_SLOT_TIMES = ["08:00", "09:00", "10:00", "11:30", "12:30", "13:30"]


def build_time_preferences(*, unavailable=None, prefer_yes=None, prefer_no=None):
    unavailable = unavailable or []
    prefer_yes = prefer_yes or []
    prefer_no = prefer_no or []

    preferences = {}
    for key in prefer_no:
        preferences[key] = TeacherTimePreferenceState.PREFER_NO
    for key in prefer_yes:
        preferences[key] = TeacherTimePreferenceState.PREFER_YES
    # Unavailable written last so it always wins over any preference on the same key.
    for key in unavailable:
        preferences[key] = TeacherTimePreferenceState.UNAVAILABLE
    return preferences


def build_subject_time_preferences(
    *, unavailable=None, prefer_yes=None, prefer_no=None
):
    unavailable = unavailable or []
    prefer_yes = prefer_yes or []
    prefer_no = prefer_no or []

    preferences = {}
    for key in prefer_no:
        preferences[key] = SubjectTimePreferenceState.PREFER_NO
    for key in prefer_yes:
        preferences[key] = SubjectTimePreferenceState.PREFER_YES
    for key in unavailable:
        preferences[key] = SubjectTimePreferenceState.UNAVAILABLE
    return preferences


def slot_keys(day_codes, times):
    return [f"{day}_{time}" for day in day_codes for time in times]


def clear_existing_data():
    """Clear all existing test data (optional - be careful in production!)"""
    print("⚠️  Clearing existing data...")
    suppress_rules = [
        (entity_type, action_type)
        for entity_type in AUDITABLE_ENTITY_TYPES
        for action_type in AuditActionType.values
    ]
    with suppress_audit_events(*suppress_rules):
        Schedule.objects.all().delete()
        Subject.objects.all().delete()
        Teacher.objects.all().delete()
        Group.objects.all().delete()
        Classroom.objects.all().delete()
        User.objects.filter(email__contains="test").delete()
        AuditEntry.objects.all().delete()
        CollaborationTeam.objects.filter(members__isnull=True).delete()
    print("✅ Existing test data cleared")


def create_users():
    """Create test users and configure stage time windows."""
    print("\n📝 Creating users...")

    users = []

    admin = User.objects.create_superuser(
        email="admin@test.com",
        password="admin123",
        name="Administrador",
        family_name="Centro",
    )
    users.append(admin)
    print(f"  ✓ Created superuser: {admin.email}")

    collaboration_data = [
        ("direccion.academica@test.com", "María", "García López"),
        ("jefatura.estudios@test.com", "Juan", "Martínez Ruiz"),
    ]

    for email, name, family_name in collaboration_data:
        collaboration_user = User.objects.create_user(
            email=email,
            password="direccion123",
            name=name,
            family_name=family_name,
        )
        users.append(collaboration_user)
        print(f"  ✓ Created collaboration user: {collaboration_user.email}")

    admin_team = CollaborationTeam.objects.create(name=f"Equipo {admin.email}")
    admin_team.members.set(users)
    for user in users:
        user.active_team = admin_team
        user.save(update_fields=["active_team"])

    # Set default stage time windows matching the onboarding defaults (STAGE_SLOT_WINDOWS).
    admin_team.schedule_config = {
        "PRESCHOOL": {
            "start_time": "09:00",
            "end_time": "14:00",
            "breaks": [
                {"start": "10:30", "end": "11:00"},
                {"start": "13:30", "end": "14:00"},
            ],
            "session_duration": 60,
        },
        "PRIMARY": {
            "start_time": "09:00",
            "end_time": "14:00",
            "breaks": [{"start": "11:30", "end": "12:00"}],
            "session_duration": 60,
        },
        "SECONDARY": {
            "start_time": "08:00",
            "end_time": "14:30",
            "breaks": [{"start": "11:00", "end": "11:30"}],
            "session_duration": 60,
        },
    }
    admin_team.save(update_fields=["schedule_config"])

    print(f"  ✓ Created collaboration team for {admin.email}: {admin_team.name}")

    return users, admin_team


def create_teachers(team):
    """Create realistic teacher catalog with varied preference patterns.

    Preference profiles for soft-constraint coverage:
      - Mañaneros fuertes (Infantil, Pri 1-2): PREFER_YES 09:00+10:00, PREFER_NO tarde
      - Tardes fuertes (Pri 3-4): PREFER_YES 12:00+13:00, PREFER_NO 09:00 → conflicto
        con asignaturas cognitivas de mañana (trade-off para el optimizador)
      - Sin preferencias (Pri 5-6, Lengua ESO, Sociales ESO, FQ ESO): baseline neutro,
        puro gap minimization
      - Mix PREFER_YES primeras + PREFER_NO última (Inglés, Mates ESO): señal fuerte
      - Unavailabilities estratégicas (EF, Inglés 1-2): hard + soft combinadas
    """
    print("\n👨‍🏫 Creating teachers...")

    teachers_data = [
        # ── Infantil tutors: mañaneros fuertes ──────────────────────────────
        (
            "infantil_1",
            "Ana Morales",
            30,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["09:00", "10:00"]),
                prefer_no=slot_keys(DAY_CODES, ["12:00", "13:00"]),
            ),
        ),
        (
            "infantil_2",
            "Marta Gil",
            30,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["09:00", "10:00"]),
                prefer_no=slot_keys(DAY_CODES, ["12:00", "13:00"]),
            ),
        ),
        (
            "infantil_3",
            "Lucía Rojas",
            30,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["09:00", "10:00"]),
                prefer_no=slot_keys(DAY_CODES, ["12:00", "13:00"]),
            ),
        ),
        # ── Primaria 1º-2º: mañaneros fuertes ───────────────────────────────
        (
            "pri_1",
            "Carlos León",
            32,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["09:00", "10:00"]),
                prefer_no=slot_keys(DAY_CODES, ["13:00"]),
            ),
        ),
        (
            "pri_2",
            "Sonia Ferrer",
            32,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["09:00", "10:00"]),
                prefer_no=slot_keys(DAY_CODES, ["12:00", "13:00"]),
            ),
        ),
        # ── Primaria 3º-4º: tardes fuertes → conflicto con asignaturas cognitivas ──
        (
            "pri_3",
            "Diego Arias",
            32,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["12:00", "13:00"]),
                prefer_no=slot_keys(DAY_CODES, ["09:00"]),
            ),
            {"max_weekly_minutes": 30},
        ),
        (
            "pri_4",
            "Raquel Núñez",
            29,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["12:00", "13:00"]),
                prefer_no=slot_keys(DAY_CODES, ["09:00", "10:00"]),
            ),
            {"weekly_hours_exact": True},
        ),
        # ── Primaria 5º-6º: sin preferencias → baseline neutro ──────────────
        (
            "pri_5",
            "Javier Ortiz",
            29,
            build_time_preferences(),
            {"max_weekly_minutes": 30, "weekly_hours_exact": True},
        ),
        (
            "pri_6",
            "Elena Varela",
            32,
            build_time_preferences(),
        ),
        # ── Inglés Primaria: prefer mañana + unavailable lun/mié 09:00 ───────
        (
            "ingles_1",
            "Paula Martín",
            35,
            build_time_preferences(
                prefer_yes=slot_keys(["TUE", "THU", "FRI"], ["09:00"])
                + slot_keys(DAY_CODES, ["10:00", "11:00"]),
                prefer_no=slot_keys(DAY_CODES, ["13:00"]),
                unavailable=slot_keys(["MON", "WED"], ["09:00"]),
            ),
        ),
        # ── Inglés ESO: prefer 09:00-10:00 + unavailable mar/jue 08:00 ───────
        (
            "ingles_2",
            "Adrián Pardo",
            30,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["09:00", "10:00"]),
                prefer_no=slot_keys(DAY_CODES, ["13:30"]),
                unavailable=slot_keys(["TUE", "THU"], ["08:00"]),
            ),
        ),
        # ── EF: unavailable lun/mié primera hora + prefer mediodía (todas etapas) ─
        # Enseña 13 grupos (26h/semana) con unavailabilities → candidatos a huecos
        (
            "ef_1",
            "Rubén Campos",
            30,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["11:00", "12:00"])
                + slot_keys(DAY_CODES, ["11:30", "12:30"]),
                prefer_no=slot_keys(DAY_CODES, ["13:00"])
                + slot_keys(DAY_CODES, ["13:30"]),
                unavailable=slot_keys(["MON", "WED"], ["09:00"])
                + slot_keys(["MON", "WED"], ["08:00"]),
            ),
        ),
        # ── Música: prefer mediodía primaria, no primera hora ────────────────
        (
            "musica",
            "Irene Salas",
            24,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["11:00", "12:00"]),
                prefer_no=slot_keys(DAY_CODES, ["09:00"]),
            ),
        ),
        # ── Plástica: prefer tarde Primaria y ESO ────────────────────────────
        (
            "plastica",
            "Noelia Prieto",
            24,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["12:00", "13:00"])
                + slot_keys(DAY_CODES, ["12:30", "13:30"]),
            ),
        ),
        # ── Religión: no última hora + unavailable viernes última ────────────
        (
            "religion",
            "Alberto Crespo",
            22,
            build_time_preferences(
                prefer_no=slot_keys(DAY_CODES, ["13:00"])
                + slot_keys(DAY_CODES, ["13:30"]),
                unavailable=slot_keys(["FRI"], ["13:00", "13:30"]),
            ),
        ),
        # ── Francés: unavailable lunes 09:00 + prefer mediodía ───────────────
        (
            "frances",
            "Clara Méndez",
            20,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["11:00", "12:00"]),
                unavailable=slot_keys(["MON"], ["09:00"]),
            ),
        ),
        # ── Mates ESO: prefer primeras horas, no última ──────────────────────
        (
            "eso_mates",
            "Sergio Vidal",
            30,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["08:00", "09:00"]),
                prefer_no=slot_keys(DAY_CODES, ["13:30"]),
            ),
        ),
        # ── Lengua ESO: sin preferencias → puro gap minimization (4 grupos) ──
        (
            "eso_lengua",
            "Beatriz Lozano",
            30,
            build_time_preferences(),
        ),
        # ── Sociales ESO: sin preferencias ───────────────────────────────────
        (
            "eso_social",
            "Víctor Sanz",
            28,
            build_time_preferences(),
        ),
        # ── Biología ESO: prefer media mañana ────────────────────────────────
        (
            "eso_bio",
            "Natalia Román",
            24,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["10:00", "11:30"]),
                prefer_no=slot_keys(DAY_CODES, ["13:30"]),
            ),
        ),
        # ── FQ ESO: sin preferencias ─────────────────────────────────────────
        (
            "eso_fq",
            "Guillermo Rey",
            24,
            build_time_preferences(),
        ),
        # ── Tecnología ESO: prefer mediodía ESO, no primera hora ─────────────
        (
            "eso_tec",
            "Héctor Plaza",
            20,
            build_time_preferences(
                prefer_yes=slot_keys(DAY_CODES, ["11:30", "12:30"]),
                prefer_no=slot_keys(DAY_CODES, ["08:00"]),
            ),
        ),
        # ── Orientación ESO: prefer_no última hora → TC distribution ─────────
        (
            "orientacion",
            "Laura Medina",
            20,
            build_time_preferences(
                prefer_no=slot_keys(DAY_CODES, ["13:30"]),
            ),
            {"max_weekly_minutes": 30, "weekly_hours_exact": True},
        ),
    ]

    teachers = {}
    for key, name, max_hours, time_preferences, *rest in teachers_data:
        extra = rest[0] if rest else {}
        teacher = Teacher.objects.create(
            name=name,
            max_weekly_hours=max_hours,
            working_hours=0,
            time_preferences=time_preferences,
            team=team,
            created_by="system",
            **extra,
        )
        teachers[key] = teacher
        mins = extra.get("max_weekly_minutes", 0)
        mode = "exactas" if extra.get("weekly_hours_exact") else "máximo"
        mins_str = f" {mins} min" if mins else ""
        print(f"  ✓ Created teacher: {teacher.name} ({max_hours} h{mins_str} {mode})")

    return teachers


def create_groups(team):
    """Create groups from 1º Infantil to 4º ESO (single line per year)."""
    print("\n👥 Creating groups...")

    groups_data = [
        ("1º Infantil", GroupEducationalStage.PRESCHOOL),
        ("2º Infantil", GroupEducationalStage.PRESCHOOL),
        ("3º Infantil", GroupEducationalStage.PRESCHOOL),
        ("1º Primaria", GroupEducationalStage.PRIMARY),
        ("2º Primaria", GroupEducationalStage.PRIMARY),
        ("3º Primaria", GroupEducationalStage.PRIMARY),
        ("4º Primaria", GroupEducationalStage.PRIMARY),
        ("5º Primaria", GroupEducationalStage.PRIMARY),
        ("6º Primaria", GroupEducationalStage.PRIMARY),
        ("1º ESO", GroupEducationalStage.SECONDARY),
        ("2º ESO", GroupEducationalStage.SECONDARY),
        ("3º ESO", GroupEducationalStage.SECONDARY),
        ("4º ESO", GroupEducationalStage.SECONDARY),
    ]

    groups = {}
    for name, stage in groups_data:
        group = Group.objects.create(
            name=name,
            stage=stage,
            team=team,
            created_by="system",
        )
        groups[name] = group
        print(f"  ✓ Created group: {group.name}")

    return groups


def create_classrooms(team):
    """Create classrooms with shared/non-shared metadata."""
    print("\n🏫 Creating classrooms...")

    classrooms_data = [
        ("Aula 1º Infantil", False),
        ("Aula 2º Infantil", False),
        ("Aula 3º Infantil", False),
        ("Aula 1º Primaria", False),
        ("Aula 2º Primaria", False),
        ("Aula 3º Primaria", False),
        ("Aula 4º Primaria", False),
        ("Aula 5º Primaria", False),
        ("Aula 6º Primaria", False),
        ("Aula 1º ESO", False),
        ("Aula 2º ESO", False),
        ("Aula 3º ESO", False),
        ("Aula 4º ESO", False),
        ("Laboratorio", True),
        ("Gimnasio", True),
        ("Aula de Música", True),
        ("Aula de Plástica", True),
        ("Aula de Tecnología", True),
    ]

    classrooms = []
    for name, is_shared in classrooms_data:
        classroom = Classroom.objects.create(
            name=name,
            is_shared=is_shared,
            team=team,
            created_by="system",
        )
        classrooms.append(classroom)
        print(
            f"  ✓ Created classroom: {classroom.name} [{'shared' if classroom.is_shared else 'exclusive'}]"
        )

    return classrooms


def create_subjects(teachers, groups, team):  # noqa: C901
    """Create realistic curriculum-focused subjects with stage-correct preference keys."""
    print("\n📚 Creating subjects...")

    # ── Preschool slot key helpers (09:00-13:00) ─────────────────────────────
    pre_morning = slot_keys(DAY_CODES, ["09:00", "10:00"])
    pre_midday = slot_keys(DAY_CODES, ["11:00", "12:00"])
    pre_late = slot_keys(DAY_CODES, ["13:00"])

    # ── Primary slot key helpers (09:00-13:00) ───────────────────────────────
    pri_morning = slot_keys(DAY_CODES, ["09:00", "10:00"])
    pri_midday = slot_keys(DAY_CODES, ["11:00", "12:00"])
    pri_afternoon = slot_keys(DAY_CODES, ["12:00", "13:00"])
    pri_last = slot_keys(DAY_CODES, ["13:00"])

    # ── Secondary slot key helpers (08:00-13:30) ─────────────────────────────
    sec_early = slot_keys(DAY_CODES, ["08:00", "09:00"])
    sec_second = slot_keys(DAY_CODES, ["09:00", "10:00"])
    sec_midday = slot_keys(DAY_CODES, ["10:00", "11:30"])
    sec_post = slot_keys(DAY_CODES, ["11:30", "12:30"])
    sec_late = slot_keys(DAY_CODES, ["12:30", "13:30"])
    sec_last = slot_keys(DAY_CODES, ["13:30"])

    subjects_data = []

    # ── Infantil (25h/semana por grupo) ──────────────────────────────────────
    for grade in ["1º Infantil", "2º Infantil", "3º Infantil"]:
        tutor_key = f"infantil_{grade[0]}"
        subjects_data.extend(
            [
                {
                    "name": f"Comunicación y Lenguaje {grade}",
                    "weekly_hours": 8,
                    "duration": 1.0,
                    "stage": EducationalStage.PRESCHOOL,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    # Cognitivo: prefer mañana, no última hora
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pre_morning,
                        prefer_no=pre_late,
                    ),
                },
                {
                    "name": f"Conocimiento del Entorno {grade}",
                    "weekly_hours": 7,
                    "duration": 1.0,
                    "stage": EducationalStage.PRESCHOOL,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    # Neutral: sin preferencias
                },
                {
                    "name": f"Crecimiento en Armonía {grade}",
                    "weekly_hours": 8,
                    "duration": 1.0,
                    "stage": EducationalStage.PRESCHOOL,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    # Neutral: sin preferencias
                },
                {
                    "name": f"Psicomotricidad {grade}",
                    "weekly_hours": 2,
                    "duration": 1.5,
                    "stage": EducationalStage.PRESCHOOL,
                    "teacher_key": "ef_1",
                    "group_name": grade,
                    # No primera hora, sí mediodía
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pre_midday,
                        prefer_no=slot_keys(DAY_CODES, ["09:00"]),
                    ),
                },
            ]
        )

    # ── Primaria 1º-4º (25 sesiones/semana) ────────────────────────────────
    for idx, grade in enumerate(
        ["1º Primaria", "2º Primaria", "3º Primaria", "4º Primaria"], start=1
    ):
        tutor_key = f"pri_{idx}"
        subjects_data.extend(
            [
                {
                    "name": f"Lengua Castellana {grade}",
                    "weekly_hours": 6,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    # Cognitivo: prefer mañana (conflicto con tutores de tarde en 3º-4º)
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_morning,
                        prefer_no=pri_last,
                    ),
                },
                {
                    "name": f"Matemáticas {grade}",
                    "weekly_hours": 5,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    # Cognitivo: prefer mañana (conflicto con tutores de tarde en 3º-4º)
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_morning,
                        prefer_no=pri_last,
                    ),
                },
                {
                    "name": f"Conocimiento del Medio {grade}",
                    "weekly_hours": 4,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    # Neutral: sin preferencias
                },
                {
                    "name": f"Inglés {grade}",
                    "weekly_hours": 3,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "ingles_1",
                    "group_name": grade,
                    # Mediodía: conflicto interesante con tutores mañaneros
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_midday,
                    ),
                },
                {
                    "name": f"Educación Física {grade}",
                    "weekly_hours": 2,
                    "duration": 1.5,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "ef_1",
                    "group_name": grade,
                    # No primera hora
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_midday,
                        prefer_no=slot_keys(DAY_CODES, ["09:00"]),
                    ),
                },
                {
                    "name": f"Música {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "musica",
                    "group_name": grade,
                    # Concuerda con preferencia de Irene
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=slot_keys(DAY_CODES, ["11:00"]),
                    ),
                },
                {
                    "name": f"Educación Artística {grade}",
                    "weekly_hours": 2,
                    "duration": 1.5,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "plastica",
                    "group_name": grade,
                    # Tarde: conflicto si el tutor del grupo prefiere mañana
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_afternoon,
                    ),
                },
                {
                    "name": f"Religión/Valores {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "religion",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_no=pri_last,
                    ),
                },
                {
                    "name": f"Tutoría {grade}",
                    "weekly_hours": 1,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                },
            ]
        )

    # ── Primaria 5º-6º con Francés ───────────────────────────────────────────
    for idx, grade in enumerate(["5º Primaria", "6º Primaria"], start=5):
        tutor_key = f"pri_{idx}"
        subjects_data.extend(
            [
                {
                    "name": f"Lengua Castellana {grade}",
                    "weekly_hours": 5,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_morning,
                        prefer_no=pri_last,
                    ),
                },
                {
                    "name": f"Matemáticas {grade}",
                    "weekly_hours": 5,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_morning,
                        prefer_no=pri_last,
                    ),
                },
                {
                    "name": f"Conocimiento del Medio {grade}",
                    "weekly_hours": 4,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    # Neutral: sin preferencias
                },
                {
                    "name": f"Inglés {grade}",
                    "weekly_hours": 3,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "ingles_1",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_midday,
                    ),
                },
                {
                    "name": f"Francés {grade}",
                    "weekly_hours": 2,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "frances",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_midday,
                    ),
                },
                {
                    "name": f"Educación Física {grade}",
                    "weekly_hours": 2,
                    "duration": 1.5,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "ef_1",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_midday,
                        prefer_no=slot_keys(DAY_CODES, ["09:00"]),
                    ),
                },
                {
                    "name": f"Música {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "musica",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=slot_keys(DAY_CODES, ["11:00"]),
                    ),
                },
                {
                    "name": f"Religión/Valores {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "religion",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_no=pri_last,
                    ),
                },
                {
                    "name": f"Educación Artística {grade}",
                    "weekly_hours": 1,
                    "duration": 1.5,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "plastica",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=pri_afternoon,
                    ),
                },
                {
                    "name": f"Tutoría {grade}",
                    "weekly_hours": 1,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                },
            ]
        )

    # ── ESO 1º-4º ────────────────────────────────────────────────────────────
    eso_block = [
        ("1º ESO", "Biología y Geología", "eso_bio", "eso_lengua"),
        ("2º ESO", "Física y Química", "eso_fq", "eso_mates"),
        ("3º ESO", "Física y Química", "eso_fq", "eso_social"),
        ("4º ESO", "Biología y Geología", "eso_bio", "eso_bio"),
    ]
    for grade, science_name, science_teacher, tutor_key in eso_block:
        subjects_data.extend(
            [
                {
                    "name": f"Lengua Castellana {grade}",
                    "weekly_hours": 5,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "eso_lengua",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=sec_early,
                    ),
                },
                {
                    "name": f"Matemáticas {grade}",
                    "weekly_hours": 4,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "eso_mates",
                    "group_name": grade,
                    # Concuerda con preferencia del profesor (08:00-09:00)
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=sec_early,
                    ),
                },
                {
                    "name": f"Inglés {grade}",
                    "weekly_hours": 4,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "ingles_2",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=sec_second,
                    ),
                },
                {
                    "name": f"Geografía e Historia {grade}",
                    "weekly_hours": 3,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "eso_social",
                    "group_name": grade,
                    # Neutral: sin preferencias (profesor también sin prefs)
                },
                {
                    "name": f"{science_name} {grade}",
                    "weekly_hours": 3,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": science_teacher,
                    "group_name": grade,
                    # Media mañana: tercera hora o post-recreo
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=sec_midday,
                    ),
                },
                {
                    "name": f"Tecnología {grade}",
                    "weekly_hours": 2,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "eso_tec",
                    "group_name": grade,
                    # Concuerda con preferencia del profesor (11:30-12:30)
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=sec_post,
                    ),
                },
                {
                    "name": f"Educación Física {grade}",
                    "weekly_hours": 2,
                    "duration": 1.5,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "ef_1",
                    "group_name": grade,
                    # No primera hora ESO
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=sec_post,
                        prefer_no=slot_keys(DAY_CODES, ["08:00"]),
                    ),
                },
                {
                    "name": f"Música/Plástica {grade}",
                    "weekly_hours": 2,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": (
                        "musica" if grade in ["1º ESO", "2º ESO"] else "plastica"
                    ),
                    "group_name": grade,
                    # Tarde: concuerda con preferencia de especialistas
                    "time_preferences": build_subject_time_preferences(
                        prefer_yes=sec_late,
                    ),
                },
                {
                    "name": f"Religión/Valores {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "religion",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(
                        prefer_no=sec_last,
                    ),
                },
                {
                    "name": f"Tutoría {grade}",
                    "weekly_hours": 1,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                },
                {
                    "name": f"Libre Elección Curricular {grade}",
                    "weekly_hours": 3,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "eso_social",
                    "group_name": grade,
                },
            ]
        )

    subjects = []
    for row in subjects_data:
        subject = Subject.objects.create(
            name=row["name"],
            weekly_hours=row["weekly_hours"],
            duration=row.get("duration", 1.0),
            preferred_time_slot=row.get("preferred_time_slot", ""),
            time_preferences=row.get("time_preferences", {}),
            type=row.get("type", SubjectType.NORMAL),
            teacher=teachers[row["teacher_key"]],
            group=groups[row["group_name"]],
            team=team,
            created_by="system",
        )
        room_name_hint = f"Aula {subject.group.name}"
        default_room = next(
            (
                room
                for room in Classroom.objects.filter(team=team)
                if room.name == room_name_hint
            ),
            None,
        )
        lower_name = subject.name.lower()
        mandatory_room = None
        if "educación física" in lower_name or "psicomotricidad" in lower_name:
            mandatory_room = Classroom.objects.filter(
                team=team, name="Gimnasio"
            ).first()
        elif "tecnología" in lower_name:
            mandatory_room = Classroom.objects.filter(
                team=team, name="Aula de Tecnología"
            ).first()
        elif "música" in lower_name:
            mandatory_room = Classroom.objects.filter(
                team=team, name="Aula de Música"
            ).first()
        elif "plástica" in lower_name or "artística" in lower_name:
            mandatory_room = Classroom.objects.filter(
                team=team, name="Aula de Plástica"
            ).first()
        elif "biología" in lower_name or "física y química" in lower_name:
            mandatory_room = Classroom.objects.filter(
                team=team, name="Laboratorio"
            ).first()

        if mandatory_room is None:
            mandatory_room = default_room

        if mandatory_room:
            subject.mandatory_classroom = mandatory_room
            subject.save(update_fields=["mandatory_classroom"])

        subjects.append(subject)
        print(
            f"  ✓ Created subject: {subject.name} "
            f"({subject.weekly_hours}h/semana, dur={subject.duration}h)"
        )

    total_hours = sum(subject.weekly_hours for subject in subjects)
    print(f"\n  📊 Total weekly hours across all groups: {total_hours}")
    return subjects


def create_admin_saved_timetable(*, users, team):
    """Create one saved timetable owned by admin user for manual testing."""
    print("\n🗓️ Creating saved timetable for admin...")

    admin_user = next((user for user in users if user.email == "admin@test.com"), None)
    if admin_user is None:
        raise RuntimeError("Admin user not found while creating saved timetable.")

    saved_name = "Horario demo admin"
    saved_observation = f"{SAVED_TIMETABLE_PREFIX}: {saved_name}"

    subjects = list(
        Subject.objects.filter(team=team)
        .select_related("teacher", "group")
        .order_by("id")[:12]
    )
    if not subjects:
        raise RuntimeError("No subjects found while creating saved admin timetable.")

    classrooms = list(Classroom.objects.filter(team=team).order_by("id"))
    if not classrooms:
        raise RuntimeError("No classrooms found while creating saved admin timetable.")

    stage_slots = build_weekly_slots()
    stage_slot_cursor = {
        "PRESCHOOL": 0,
        "PRIMARY": 0,
        "SECONDARY": 0,
    }
    stage_slot_indices = {
        "PRESCHOOL": [
            idx
            for idx, slot in enumerate(stage_slots)
            if slot.get("stage") == "PRESCHOOL"
        ],
        "PRIMARY": [
            idx
            for idx, slot in enumerate(stage_slots)
            if slot.get("stage") == "PRIMARY"
        ],
        "SECONDARY": [
            idx
            for idx, slot in enumerate(stage_slots)
            if slot.get("stage") == "SECONDARY"
        ],
    }

    created = []
    for subject in subjects:
        stage_code = session_stage_code(
            session={"group": subject.group, "subject": subject}
        )
        slot_pool = stage_slot_indices.get(stage_code) or stage_slot_indices["PRIMARY"]
        cursor = stage_slot_cursor.get(stage_code, 0)
        if cursor >= len(slot_pool):
            cursor = 0
        slot_idx = slot_pool[cursor]
        stage_slot_cursor[stage_code] = cursor + 1

        slot = stage_slots[slot_idx]
        start_time = slot["start"]
        end_time = slot["end"]

        classroom = subject.mandatory_classroom or classrooms[0]

        schedule = Schedule.objects.create(
            name=saved_name,
            start_time=start_time,
            end_time=end_time,
            observations=saved_observation,
            team=team,
            teacher=subject.teacher,
            classroom=classroom,
            group=subject.group,
            subject=subject,
            created_by=admin_user.email,
            updated_by="system",
        )
        schedule.users.add(admin_user)
        created.append(schedule)

    print(f"  ✓ Created saved timetable for admin with {len(created)} sessions")
    return created


def main():
    """Main function to load all test data"""
    print("🚀 Starting test data load...")
    print("=" * 60)

    try:
        clear_existing_data()

        users, demo_team = create_users()
        teachers = create_teachers(demo_team)
        groups = create_groups(demo_team)
        classrooms = create_classrooms(demo_team)
        subjects = create_subjects(teachers, groups, demo_team)
        saved_admin_timetable = create_admin_saved_timetable(
            users=users,
            team=demo_team,
        )

        print("\n" + "=" * 60)
        print("✅ Test data loaded successfully!")
        print("\n📊 Summary:")
        print(f"  • {len(users)} users created")
        print("  • 1 collaboration team created")
        print(f"  • {len(teachers)} teachers created")
        print(f"  • {len(subjects)} subjects created")
        print(f"  • {len(classrooms)} classrooms created")
        print(f"  • {len(groups)} groups created")
        print(f"  • {len(saved_admin_timetable)} saved schedules for admin")
        print("\n🔑 Login credentials:")
        print("  Admin: admin@test.com / admin123")
        print("  Dirección: direccion.academica@test.com / direccion123")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error loading test data: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
