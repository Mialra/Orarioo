"""
Script to load test data into all entities for easy testing.
Run from the src directory with: python load_test_data.py

Dataset target:
- 1º, 2º, 3º de Infantil
- 1º a 6º de Primaria
- 1º a 4º de ESO
- One group per year (no A/B split)
"""

import os
import sys

# Add the src directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

# NOTE: These imports must come after django.setup() - ignore E402
from django.contrib.auth import get_user_model  # noqa: E402

from classroom.models import Classroom  # noqa: E402
from group.models import EducationalStage as GroupEducationalStage  # noqa: E402
from group.models import Group  # noqa: E402
from schedule.models import Schedule  # noqa: E402
from subject.models import (  # noqa: E402
    EducationalStage,
    Subject,
    SubjectTimePreferenceState,
    SubjectType,
)
from teacher.models import Teacher, TeacherTimePreferenceState  # noqa: E402

User = get_user_model()

DAY_CODES = ["MON", "TUE", "WED", "THU", "FRI"]
SLOT_TIMES = ["08:30", "09:30", "10:30", "12:00", "13:00", "14:00"]


def build_time_preferences(*, unavailable=None, prefer_yes=None, prefer_no=None):
    unavailable = unavailable or []
    prefer_yes = prefer_yes or []
    prefer_no = prefer_no or []

    preferences = {}
    for key in unavailable:
        preferences[key] = TeacherTimePreferenceState.UNAVAILABLE
    for key in prefer_yes:
        preferences[key] = TeacherTimePreferenceState.PREFER_YES
    for key in prefer_no:
        preferences[key] = TeacherTimePreferenceState.PREFER_NO
    return preferences


def build_subject_time_preferences(*, unavailable=None, prefer_yes=None, prefer_no=None):
    unavailable = unavailable or []
    prefer_yes = prefer_yes or []
    prefer_no = prefer_no or []

    preferences = {}
    for key in unavailable:
        preferences[key] = SubjectTimePreferenceState.UNAVAILABLE
    for key in prefer_yes:
        preferences[key] = SubjectTimePreferenceState.PREFER_YES
    for key in prefer_no:
        preferences[key] = SubjectTimePreferenceState.PREFER_NO
    return preferences


def slot_keys(day_codes, times):
    return [f"{day}_{time}" for day in day_codes for time in times]


def clear_existing_data():
    """Clear all existing test data (optional - be careful in production!)"""
    print("⚠️  Clearing existing data...")
    Schedule.objects.all().delete()
    Subject.objects.all().delete()
    Teacher.objects.all().delete()
    Group.objects.all().delete()
    Classroom.objects.all().delete()
    User.objects.filter(email__contains="test").delete()
    print("✅ Existing test data cleared")


def create_users():
    """Create test users"""
    print("\n📝 Creating users...")

    users = []

    # Create superuser/administrator for timetable generation ownership.
    admin = User.objects.create_superuser(
        email="admin@test.com",
        password="admin123",
        name="Administrador",
        family_name="Centro",
    )
    users.append(admin)
    print(f"  ✓ Created administrator: {admin.email}")

    # Directors for audit/review flow.
    directors_data = [
        ("direccion.academica@test.com", "María", "García López"),
        ("jefatura.estudios@test.com", "Juan", "Martínez Ruiz"),
    ]

    for email, name, family_name in directors_data:
        director = User.objects.create_user(
            email=email,
            password="director123",
            name=name,
            family_name=family_name,
            role="director",
        )
        users.append(director)
        print(f"  ✓ Created director: {director.email}")

    return users


def create_teachers():
    """Create realistic teacher catalog with availability constraints."""
    print("\n👨‍🏫 Creating teachers...")

    early_slots = slot_keys(["MON", "TUE", "WED", "THU", "FRI"], ["08:30", "09:30"])
    last_slot = slot_keys(DAY_CODES, ["14:00"])

    teachers_data = [
        ("infantil_1", "Tutoría Infantil 1", 30, build_time_preferences(prefer_yes=early_slots[:5])),
        ("infantil_2", "Tutoría Infantil 2", 30, build_time_preferences(prefer_yes=early_slots[:5])),
        ("infantil_3", "Tutoría Infantil 3", 30, build_time_preferences(prefer_yes=early_slots[:5])),
        ("pri_1", "Tutoría Primaria 1", 32, build_time_preferences(prefer_yes=early_slots[:6])),
        ("pri_2", "Tutoría Primaria 2", 32, build_time_preferences(prefer_yes=early_slots[:6])),
        ("pri_3", "Tutoría Primaria 3", 32, build_time_preferences(prefer_yes=early_slots[:6])),
        ("pri_4", "Tutoría Primaria 4", 32, build_time_preferences(prefer_yes=early_slots[:6])),
        ("pri_5", "Tutoría Primaria 5", 32, build_time_preferences(prefer_yes=early_slots[:6])),
        ("pri_6", "Tutoría Primaria 6", 32, build_time_preferences(prefer_yes=early_slots[:6])),
        ("ingles_1", "Inglés Primaria", 35, build_time_preferences(unavailable=slot_keys(["MON", "WED"], ["08:30"]))),
        ("ingles_2", "Inglés ESO", 30, build_time_preferences(unavailable=slot_keys(["TUE", "THU"], ["08:30"]))),
        ("ef_1", "Educación Física", 30, build_time_preferences(unavailable=early_slots[:8], prefer_yes=slot_keys(DAY_CODES, ["12:00", "13:00"]))),
        ("musica", "Música", 24, build_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["10:30", "12:00"]))),
        ("plastica", "Educación Artística", 24, build_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["12:00", "13:00"]))),
        ("religion", "Religión/Valores", 22, build_time_preferences(unavailable=slot_keys(["FRI"], ["14:00"]))),
        ("frances", "Francés", 20, build_time_preferences(unavailable=slot_keys(["MON"], ["08:30"]))),
        ("eso_mates", "Matemáticas ESO", 30, build_time_preferences(prefer_yes=early_slots[:8])),
        ("eso_lengua", "Lengua ESO", 30, build_time_preferences(prefer_yes=early_slots[:8])),
        ("eso_social", "Geografía e Historia ESO", 28, build_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["09:30", "10:30"]))),
        ("eso_bio", "Biología y Geología", 24, build_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["10:30", "12:00"]))),
        ("eso_fq", "Física y Química", 24, build_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["10:30", "12:00"]))),
        ("eso_tec", "Tecnología", 20, build_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["12:00", "13:00"]))),
        ("orientacion", "Orientación", 20, build_time_preferences(prefer_no=last_slot)),
    ]

    teachers = {}
    for key, name, max_hours, time_preferences in teachers_data:
        teacher = Teacher.objects.create(
            name=name,
            max_weekly_hours=max_hours,
            working_hours=0,
            time_preferences=time_preferences,
            created_by="system",
        )
        teachers[key] = teacher
        print(f"  ✓ Created teacher: {teacher.name}")

    return teachers


def create_groups():
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
        group = Group.objects.create(name=name, stage=stage, created_by="system")
        groups[name] = group
        print(f"  ✓ Created group: {group.name}")

    return groups


def create_classrooms():
    """Create classrooms with realistic room types."""
    print("\n🏫 Creating classrooms...")

    classrooms_data = [
        ("Aula 1º Infantil", "EARLY"),
        ("Aula 2º Infantil", "EARLY"),
        ("Aula 3º Infantil", "EARLY"),
        ("Aula 1º Primaria", "STANDARD"),
        ("Aula 2º Primaria", "STANDARD"),
        ("Aula 3º Primaria", "STANDARD"),
        ("Aula 4º Primaria", "STANDARD"),
        ("Aula 5º Primaria", "STANDARD"),
        ("Aula 6º Primaria", "STANDARD"),
        ("Aula 1º ESO", "STANDARD"),
        ("Aula 2º ESO", "STANDARD"),
        ("Aula 3º ESO", "STANDARD"),
        ("Aula 4º ESO", "STANDARD"),
        ("Laboratorio", "LAB"),
        ("Gimnasio", "GYM"),
        ("Aula de Música", "MUSIC"),
        ("Aula de Plástica", "ART"),
        ("Aula de Tecnología", "TECH"),
    ]

    classrooms = []
    for name, classroom_type in classrooms_data:
        classroom = Classroom.objects.create(
            name=name,
            classroom_type=classroom_type,
            created_by="system",
        )
        classrooms.append(classroom)
        print(f"  ✓ Created classroom: {classroom.name} [{classroom.classroom_type}]")

    return classrooms


def create_subjects(teachers, groups):
    """Create realistic curriculum-focused subjects, emphasizing Primary complexity."""
    print("\n📚 Creating subjects...")

    morning_keys = slot_keys(DAY_CODES, ["08:30", "09:30", "10:30"])
    midday_keys = slot_keys(DAY_CODES, ["12:00", "13:00"])
    late_keys = slot_keys(DAY_CODES, ["14:00"])

    subjects_data = []

    # Infantil (25h/semana por grupo)
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
                    "time_preferences": build_subject_time_preferences(prefer_yes=morning_keys[:10]),
                },
                {
                    "name": f"Conocimiento del Entorno {grade}",
                    "weekly_hours": 7,
                    "duration": 1.0,
                    "stage": EducationalStage.PRESCHOOL,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(prefer_yes=midday_keys),
                },
                {
                    "name": f"Crecimiento en Armonía {grade}",
                    "weekly_hours": 8,
                    "duration": 1.0,
                    "stage": EducationalStage.PRESCHOOL,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                },
                {
                    "name": f"Psicomotricidad {grade}",
                    "weekly_hours": 2,
                    "duration": 1.5,
                    "stage": EducationalStage.PRESCHOOL,
                    "teacher_key": "ef_1",
                    "group_name": grade,
                    "required_classroom_type": "GYM",
                    "time_preferences": build_subject_time_preferences(prefer_yes=midday_keys, prefer_no=late_keys),
                },
            ]
        )

    # Primaria 1º-4º (25h/semana) - emphasizes mixed durations.
    for idx, grade in enumerate(["1º Primaria", "2º Primaria", "3º Primaria", "4º Primaria"], start=1):
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
                    "time_preferences": build_subject_time_preferences(prefer_yes=morning_keys),
                },
                {
                    "name": f"Matemáticas {grade}",
                    "weekly_hours": 5,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["08:30", "09:30"]), prefer_no=late_keys),
                },
                {
                    "name": f"Conocimiento del Medio {grade}",
                    "weekly_hours": 4,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                },
                {
                    "name": f"Inglés {grade}",
                    "weekly_hours": 3,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "ingles_1",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(prefer_yes=midday_keys),
                },
                {
                    "name": f"Educación Física {grade}",
                    "weekly_hours": 2,
                    "duration": 1.5,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "ef_1",
                    "group_name": grade,
                    "required_classroom_type": "GYM",
                    "time_preferences": build_subject_time_preferences(prefer_yes=midday_keys, prefer_no=slot_keys(DAY_CODES, ["08:30"])),
                },
                {
                    "name": f"Música {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "musica",
                    "group_name": grade,
                    "required_classroom_type": "MUSIC",
                    "time_preferences": build_subject_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["12:00"])),
                },
                {
                    "name": f"Educación Artística {grade}",
                    "weekly_hours": 2,
                    "duration": 1.5,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "plastica",
                    "group_name": grade,
                    "required_classroom_type": "ART",
                    "time_preferences": build_subject_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["12:00", "13:00"])),
                },
                {
                    "name": f"Religión/Valores {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "religion",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(prefer_no=slot_keys(DAY_CODES, ["14:00"])),
                },
                {
                    "name": f"Tutoría {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    "type": SubjectType.TC,
                },
            ]
        )

    # Primaria 5º-6º with French and more split sessions.
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
                    "time_preferences": build_subject_time_preferences(prefer_yes=morning_keys),
                },
                {
                    "name": f"Matemáticas {grade}",
                    "weekly_hours": 5,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["08:30", "09:30"])) ,
                },
                {
                    "name": f"Conocimiento del Medio {grade}",
                    "weekly_hours": 4,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                },
                {
                    "name": f"Inglés {grade}",
                    "weekly_hours": 3,
                    "duration": 1.0,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "ingles_1",
                    "group_name": grade,
                },
                {
                    "name": f"Francés {grade}",
                    "weekly_hours": 2,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "frances",
                    "group_name": grade,
                    "time_preferences": build_subject_time_preferences(prefer_yes=midday_keys),
                },
                {
                    "name": f"Educación Física {grade}",
                    "weekly_hours": 2,
                    "duration": 1.5,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "ef_1",
                    "group_name": grade,
                    "required_classroom_type": "GYM",
                },
                {
                    "name": f"Música {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "musica",
                    "group_name": grade,
                    "required_classroom_type": "MUSIC",
                },
                {
                    "name": f"Religión/Valores {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "religion",
                    "group_name": grade,
                },
                {
                    "name": f"Educación Artística {grade}",
                    "weekly_hours": 1,
                    "duration": 1.5,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": "plastica",
                    "group_name": grade,
                    "required_classroom_type": "ART",
                },
                {
                    "name": f"Tutoría {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.PRIMARY,
                    "teacher_key": tutor_key,
                    "group_name": grade,
                    "type": SubjectType.TC,
                },
            ]
        )

    # ESO 1º-4º (30h/semana)
    eso_block = [
        ("1º ESO", "Biología y Geología", "eso_bio"),
        ("2º ESO", "Física y Química", "eso_fq"),
        ("3º ESO", "Física y Química", "eso_fq"),
        ("4º ESO", "Biología y Geología", "eso_bio"),
    ]
    for grade, science_name, science_teacher in eso_block:
        subjects_data.extend(
            [
                {
                    "name": f"Lengua Castellana {grade}",
                    "weekly_hours": 5,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "eso_lengua",
                    "group_name": grade,
                },
                {
                    "name": f"Matemáticas {grade}",
                    "weekly_hours": 4,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "eso_mates",
                    "group_name": grade,
                },
                {
                    "name": f"Inglés {grade}",
                    "weekly_hours": 4,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "ingles_2",
                    "group_name": grade,
                },
                {
                    "name": f"Geografía e Historia {grade}",
                    "weekly_hours": 3,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "eso_social",
                    "group_name": grade,
                },
                {
                    "name": f"{science_name} {grade}",
                    "weekly_hours": 3,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": science_teacher,
                    "group_name": grade,
                    "required_classroom_type": "LAB",
                    "time_preferences": build_subject_time_preferences(prefer_yes=slot_keys(DAY_CODES, ["10:30", "12:00"])),
                },
                {
                    "name": f"Tecnología {grade}",
                    "weekly_hours": 2,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "eso_tec",
                    "group_name": grade,
                    "required_classroom_type": "TECH",
                },
                {
                    "name": f"Educación Física {grade}",
                    "weekly_hours": 2,
                    "duration": 1.5,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "ef_1",
                    "group_name": grade,
                    "required_classroom_type": "GYM",
                },
                {
                    "name": f"Música/Plástica {grade}",
                    "weekly_hours": 2,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "musica" if grade in ["1º ESO", "2º ESO"] else "plastica",
                    "group_name": grade,
                    "required_classroom_type": "MUSIC" if grade in ["1º ESO", "2º ESO"] else "ART",
                },
                {
                    "name": f"Tutoría {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "orientacion",
                    "group_name": grade,
                    "type": SubjectType.TC,
                },
                {
                    "name": f"Religión/Valores {grade}",
                    "weekly_hours": 1,
                    "duration": 0.75,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "religion",
                    "group_name": grade,
                },
                {
                    "name": f"Proyecto Interdisciplinar {grade}",
                    "weekly_hours": 3,
                    "duration": 1.0,
                    "stage": EducationalStage.SECONDARY,
                    "teacher_key": "orientacion",
                    "group_name": grade,
                    "type": SubjectType.TC,
                    "time_preferences": build_subject_time_preferences(prefer_yes=midday_keys, prefer_no=slot_keys(DAY_CODES, ["08:30"])),
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
            required_classroom_type=row.get("required_classroom_type", ""),
            time_preferences=row.get("time_preferences", {}),
            stage=row["stage"],
            type=row.get("type", SubjectType.NORMAL),
            teacher=teachers[row["teacher_key"]],
            group=groups[row["group_name"]],
            created_by="system",
        )
        subjects.append(subject)
        print(
            f"  ✓ Created subject: {subject.name} "
            f"({subject.weekly_hours}h/semana, dur={subject.duration}h)"
        )

    total_hours = sum(subject.weekly_hours for subject in subjects)
    print(
        f"\n  📊 Total weekly hours across all groups: {total_hours}"
    )
    return subjects


def main():
    """Main function to load all test data"""
    print("🚀 Starting test data load...")
    print("=" * 60)

    try:
        clear_existing_data()

        # Create all entities
        users = create_users()
        teachers = create_teachers()
        groups = create_groups()
        classrooms = create_classrooms()
        subjects = create_subjects(teachers, groups)
        # schedules = create_schedules(teachers, subjects, classrooms, groups, users)

        print("\n" + "=" * 60)
        print("✅ Test data loaded successfully!")
        print("\n📊 Summary:")
        print(f"  • {len(users)} users created")
        print(f"  • {len(teachers)} teachers created")
        print(f"  • {len(subjects)} subjects created")
        print(f"  • {len(classrooms)} classrooms created")
        print(f"  • {len(groups)} groups created")
        # print(f"  • {len(schedules)} schedules created")
        print("\n🔑 Login credentials:")
        print("  Admin: admin@test.com / admin123")
        print("  Dirección: direccion.academica@test.com / director123")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error loading test data: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
