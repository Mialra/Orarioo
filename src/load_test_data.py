"""
Script to load test data into all entities for easy testing.
Run from the src directory with: python load_test_data.py
"""

import os
import sys
from datetime import timedelta

# Add the src directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import django  # noqa: E402
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

# NOTE: These imports must come after django.setup() - ignore E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402
from classroom.models import Classroom  # noqa: E402
from group.models import EducationalStage as GroupEducationalStage  # noqa: E402
from group.models import Group  # noqa: E402
from schedule.models import Schedule  # noqa: E402
from subject.models import EducationalStage, Subject, SubjectType  # noqa: E402
from teacher.models import Teacher  # noqa: E402

User = get_user_model()


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

    # Create superuser/administrator
    admin = User.objects.create_superuser(
        email="admin@test.com", password="admin123", name="Admin", family_name="Test"
    )
    users.append(admin)
    print(f"  ✓ Created administrator: {admin.email}")

    # Create directors
    directors_data = [
        ("director1@test.com", "María", "García López"),
        ("director2@test.com", "Juan", "Martínez Ruiz"),
        ("director3@test.com", "Ana", "Fernández Sánchez"),
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
    """Create test teachers"""
    print("\n👨‍🏫 Creating teachers...")

    teachers_data = [
        ("Prof. Carlos Rodríguez", 25, "Matemáticas"),
        ("Prof. Laura Jiménez", 20, "Lengua"),
        ("Prof. Miguel Sánchez", 22, "Inglés"),
        ("Prof. Elena Torres", 18, "Ciencias Naturales"),
        ("Prof. David López", 20, "Educación Física"),
        ("Prof. Carmen Díaz", 18, "Música"),
        ("Prof. Antonio Ruiz", 20, "Plástica"),
        ("Prof. Isabel Moreno", 22, "Historia"),
    ]

    teachers = []
    for name, max_hours, preferences in teachers_data:
        teacher = Teacher.objects.create(
            name=name,
            max_weekly_hours=max_hours,
            working_hours=0,
            preferences=preferences,
            availability="Lunes a Viernes: 8:00-14:00",
            unavailability="Miércoles 12:00-14:00",
            created_by="system",
        )
        teachers.append(teacher)
        print(f"  ✓ Created teacher: {teacher.name}")

    return teachers


def create_subjects(teachers):
    """Create test subjects"""
    print("\n📚 Creating subjects...")

    subjects_data = [
        # Primary subjects
        ("Matemáticas 1º", 5, 1.0, EducationalStage.PRIMARY, SubjectType.NORMAL, 0),
        ("Lengua 1º", 5, 1.0, EducationalStage.PRIMARY, SubjectType.NORMAL, 1),
        ("Inglés 1º", 3, 1.0, EducationalStage.PRIMARY, SubjectType.NORMAL, 2),
        (
            "Ciencias Naturales 1º",
            3,
            1.0,
            EducationalStage.PRIMARY,
            SubjectType.NORMAL,
            3,
        ),
        (
            "Educación Física 1º",
            2,
            1.0,
            EducationalStage.PRIMARY,
            SubjectType.NORMAL,
            4,
        ),
        ("Matemáticas 2º", 5, 1.0, EducationalStage.PRIMARY, SubjectType.NORMAL, 0),
        ("Lengua 2º", 5, 1.0, EducationalStage.PRIMARY, SubjectType.NORMAL, 1),
        ("Inglés 2º", 3, 1.0, EducationalStage.PRIMARY, SubjectType.NORMAL, 2),
        # Secondary subjects
        (
            "Matemáticas Avanzadas",
            4,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            0,
        ),
        (
            "Lengua Castellana",
            4,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            1,
        ),
        (
            "Historia Universal",
            3,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            7,
        ),
        # Preschool subjects
        ("Música Infantil", 2, 0.5, EducationalStage.PRESCHOOL, SubjectType.NORMAL, 5),
        (
            "Plástica Infantil",
            2,
            0.5,
            EducationalStage.PRESCHOOL,
            SubjectType.NORMAL,
            6,
        ),
        # TC subjects
        ("Tutoría 1º", 2, 1.0, EducationalStage.PRIMARY, SubjectType.TC, 0),
        ("Tutoría 2º", 2, 1.0, EducationalStage.PRIMARY, SubjectType.TC, 1),
    ]

    subjects = []
    for name, weekly_hours, duration, stage, sub_type, teacher_idx in subjects_data:
        subject = Subject.objects.create(
            name=name,
            weekly_hours=weekly_hours,
            duration=duration,
            preferred_time_slot="9:00-10:00" if "Matemáticas" in name else "",
            stage=stage,
            type=sub_type,
            teacher=teachers[teacher_idx],
            created_by="system",
        )
        subjects.append(subject)
        print(f"  ✓ Created subject: {subject.name}")

    return subjects


def create_classrooms():
    """Create test classrooms"""
    print("\n🏫 Creating classrooms...")

    classrooms_data = [
        "Aula 101",
        "Aula 102",
        "Aula 103",
        "Aula 201",
        "Aula 202",
        "Aula 203",
        "Laboratorio",
        "Gimnasio",
        "Aula de Música",
        "Aula de Plástica",
    ]

    classrooms = []
    for name in classrooms_data:
        classroom = Classroom.objects.create(name=name, created_by="system")
        classrooms.append(classroom)
        print(f"  ✓ Created classroom: {classroom.name}")

    return classrooms


def create_groups():
    """Create test groups"""
    print("\n👥 Creating groups...")

    groups_data = [
        ("1º Primaria A", GroupEducationalStage.PRIMARY),
        ("1º Primaria B", GroupEducationalStage.PRIMARY),
        ("2º Primaria A", GroupEducationalStage.PRIMARY),
        ("3º Primaria A", GroupEducationalStage.PRIMARY),
        ("1º ESO A", GroupEducationalStage.SECONDARY),
        ("2º ESO A", GroupEducationalStage.SECONDARY),
        ("Infantil 3 años", GroupEducationalStage.PRESCHOOL),
        ("Infantil 4 años", GroupEducationalStage.PRESCHOOL),
    ]

    groups = []
    for name, stage in groups_data:
        group = Group.objects.create(name=name, stage=stage, created_by="system")
        groups.append(group)
        print(f"  ✓ Created group: {group.name}")

    return groups


def create_schedules(teachers, subjects, classrooms, groups, users):
    """Create test schedules"""
    print("\n📅 Creating schedules...")

    # Base date - next Monday at 9:00 (timezone-aware)
    today = timezone.now()
    days_ahead = 0 - today.weekday()  # Monday is weekday 0
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    next_monday = today + timedelta(days_ahead)
    base_date = next_monday.replace(hour=9, minute=0, second=0, microsecond=0)

    schedules = []

    # Create a week of schedules
    schedule_data = [
        # Monday
        (
            0,
            9,
            0,
            "Matemáticas 1º - Lunes",
            subjects[0],
            teachers[0],
            classrooms[0],
            groups[0],
        ),
        (
            0,
            10,
            0,
            "Lengua 1º - Lunes",
            subjects[1],
            teachers[1],
            classrooms[0],
            groups[0],
        ),
        (
            0,
            11,
            0,
            "Inglés 1º - Lunes",
            subjects[2],
            teachers[2],
            classrooms[0],
            groups[0],
        ),
        # Tuesday
        (
            1,
            9,
            0,
            "Matemáticas 2º - Martes",
            subjects[5],
            teachers[0],
            classrooms[1],
            groups[2],
        ),
        (
            1,
            10,
            0,
            "Lengua 2º - Martes",
            subjects[6],
            teachers[1],
            classrooms[1],
            groups[2],
        ),
        (
            1,
            12,
            0,
            "Educación Física 1º",
            subjects[4],
            teachers[4],
            classrooms[7],
            groups[0],
        ),
        # Wednesday
        (
            2,
            9,
            0,
            "Ciencias Naturales 1º",
            subjects[3],
            teachers[3],
            classrooms[0],
            groups[0],
        ),
        (
            2,
            10,
            0,
            "Música Infantil",
            subjects[11],
            teachers[5],
            classrooms[8],
            groups[6],
        ),
        # Thursday
        (
            3,
            9,
            0,
            "Matemáticas Avanzadas",
            subjects[8],
            teachers[0],
            classrooms[3],
            groups[4],
        ),
        (
            3,
            10,
            0,
            "Historia Universal",
            subjects[10],
            teachers[7],
            classrooms[3],
            groups[4],
        ),
        # Friday
        (
            4,
            9,
            0,
            "Plástica Infantil",
            subjects[12],
            teachers[6],
            classrooms[9],
            groups[7],
        ),
        (4, 11, 0, "Inglés 2º", subjects[7], teachers[2], classrooms[1], groups[2]),
    ]

    for (
        day_offset,
        hour,
        teacher_idx,
        name,
        subject,
        teacher,
        classroom,
        group,
    ) in schedule_data:
        start_time = base_date + timedelta(days=day_offset, hours=hour - 9)
        end_time = start_time + timedelta(hours=subject.duration)

        schedule = Schedule.objects.create(
            name=name,
            start_time=start_time,
            end_time=end_time,
            observations=f"Clase regular de {subject.name}",
            teacher=teacher,
            classroom=classroom,
            group=group,
            subject=subject,
            created_by="system",
        )

        # Add some users to the schedule
        if users:
            schedule.users.add(users[0])  # Add admin
            if len(users) > 1:
                schedule.users.add(users[1])  # Add first director

        schedules.append(schedule)
        print(
            f"  ✓ Created schedule: {schedule.name} - {schedule.start_time.strftime('%A %H:%M')}"
        )

    return schedules


def main():
    """Main function to load all test data"""
    print("🚀 Starting test data load...")
    print("=" * 60)

    try:
        clear_existing_data()

        # Create all entities
        users = create_users()
        teachers = create_teachers()
        subjects = create_subjects(teachers)
        classrooms = create_classrooms()
        groups = create_groups()
        schedules = create_schedules(teachers, subjects, classrooms, groups, users)

        print("\n" + "=" * 60)
        print("✅ Test data loaded successfully!")
        print("\n📊 Summary:")
        print(f"  • {len(users)} users created")
        print(f"  • {len(teachers)} teachers created")
        print(f"  • {len(subjects)} subjects created")
        print(f"  • {len(classrooms)} classrooms created")
        print(f"  • {len(groups)} groups created")
        print(f"  • {len(schedules)} schedules created")
        print("\n🔑 Login credentials:")
        print("  Admin: admin@test.com / admin123")
        print("  Director: director1@test.com / director123")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error loading test data: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
