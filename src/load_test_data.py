"""
Script to load test data into all entities for easy testing.
Run from the src directory with: python load_test_data.py
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
    """Create test teachers for ESO subjects"""
    print("\n👨‍🏫 Creating teachers...")

    teachers_data = [
        ("Prof. Carlos Rodríguez", 20, "Matemáticas"),
        ("Prof. Laura Jiménez", 20, "Lengua Castellana"),
        ("Prof. Miguel Sánchez", 18, "Inglés"),
        ("Prof. Elena Torres", 18, "Biología y Geología"),
        ("Prof. Isabel Moreno", 18, "Geografía e Historia"),
        ("Prof. David López", 15, "Educación Física"),
        ("Prof. Carmen Díaz", 15, "Música"),
        ("Prof. Antonio Ruiz", 15, "Educación Plástica"),
    ]

    teachers = []
    for name, max_hours, _preferences in teachers_data:
        teacher = Teacher.objects.create(
            name=name,
            max_weekly_hours=max_hours,
            working_hours=0,
            created_by="system",
        )
        teachers.append(teacher)
        print(f"  ✓ Created teacher: {teacher.name}")

    return teachers


def create_subjects(teachers, groups):
    """Create test subjects for 1º ESO and 2º ESO"""
    print("\n📚 Creating subjects...")

    # Realistic subjects for Spanish ESO (Educación Secundaria Obligatoria)
    # Each ESO year has 6 subjects with 5 hours/week = 30 hours/week (6 hours/day × 5 days)
    # Format: (name, weekly_hours, duration, stage, type, teacher_index, group_index)
    subjects_data = [
        # 1º ESO subjects (6 subjects × 5 hours = 30 hours total)
        (
            "Matemáticas 1º ESO",
            5,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            0,
            0,
        ),
        (
            "Lengua Castellana 1º ESO",
            5,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            1,
            0,
        ),
        ("Inglés 1º ESO", 5, 1.0, EducationalStage.SECONDARY, SubjectType.NORMAL, 2, 0),
        (
            "Biología y Geología 1º ESO",
            5,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            3,
            0,
        ),
        (
            "Geografía e Historia 1º ESO",
            5,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            4,
            0,
        ),
        (
            "Educación Física 1º ESO",
            5,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            5,
            0,
        ),
        # 2º ESO subjects (6 subjects × 5 hours = 30 hours total)
        (
            "Matemáticas 2º ESO",
            5,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            0,
            1,
        ),
        (
            "Lengua Castellana 2º ESO",
            5,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            1,
            1,
        ),
        ("Inglés 2º ESO", 5, 1.0, EducationalStage.SECONDARY, SubjectType.NORMAL, 2, 1),
        (
            "Física y Química 2º ESO",
            5,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            3,
            1,
        ),
        (
            "Geografía e Historia 2º ESO",
            5,
            1.0,
            EducationalStage.SECONDARY,
            SubjectType.NORMAL,
            4,
            1,
        ),
        ("Música 2º ESO", 5, 1.0, EducationalStage.SECONDARY, SubjectType.NORMAL, 6, 1),
    ]

    subjects = []
    for (
        name,
        weekly_hours,
        duration,
        stage,
        sub_type,
        teacher_idx,
        group_idx,
    ) in subjects_data:
        subject = Subject.objects.create(
            name=name,
            weekly_hours=weekly_hours,
            duration=duration,
            preferred_time_slot="8:30-11:30" if "Matemáticas" in name else "",
            stage=stage,
            type=sub_type,
            teacher=teachers[teacher_idx],
            group=groups[group_idx],
            created_by="system",
        )
        subjects.append(subject)
        print(f"  ✓ Created subject: {subject.name} ({weekly_hours}h/semana)")

    total_hours = sum(s.weekly_hours for s in subjects)
    print(
        f"\n  📊 Total weekly hours: {total_hours} (6 hours/day × 5 days = 30 slots per group)"
    )
    return subjects


def create_classrooms():
    """Create test classrooms for ESO"""
    print("\n🏫 Creating classrooms...")

    classrooms_data = [
        "Aula 1º ESO A",
        "Aula 2º ESO A",
        "Laboratorio",
        "Gimnasio",
        "Aula de Música",
        "Aula de Informática",
    ]

    classrooms = []
    for name in classrooms_data:
        classroom = Classroom.objects.create(name=name, created_by="system")
        classrooms.append(classroom)
        print(f"  ✓ Created classroom: {classroom.name}")

    return classrooms


def create_groups():
    """Create test groups for 1º and 2º ESO"""
    print("\n👥 Creating groups...")

    groups_data = [
        ("1º ESO A", GroupEducationalStage.SECONDARY),
        ("2º ESO A", GroupEducationalStage.SECONDARY),
    ]

    groups = []
    for name, stage in groups_data:
        group = Group.objects.create(name=name, stage=stage, created_by="system")
        groups.append(group)
        print(f"  ✓ Created group: {group.name}")

    return groups


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
        subjects = create_subjects(teachers, groups)
        classrooms = create_classrooms()
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
        print("  Director: director1@test.com / director123")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error loading test data: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
