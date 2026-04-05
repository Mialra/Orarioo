#!/usr/bin/env python
"""Test schedule generation with large realistic dataset (345 sessions)"""

import os
import sys
import time

import django

# Setup Django
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from schedule.algorithm.generator import BasicScheduleGenerator  # noqa: E402
from schedule.algorithm.slots import build_weekly_slots  # noqa: E402

User = get_user_model()


def test_schedule_generation():
    """Generate schedule with all loaded data."""
    total_slots = len(build_weekly_slots())
    print("\n" + "=" * 70)
    print("🚀 TESTING SCHEDULE GENERATION WITH CURRENT DATASET")
    print("=" * 70)

    admin = User.objects.filter(email="admin@test.com").first()
    if not admin:
        print("❌ Admin user not found. Run load_test_data.py first.")
        sys.exit(1)

    print(f"\n👤 Using admin: {admin.email}")

    active_team = admin.active_team or admin.collaboration_teams.order_by("id").first()
    if not active_team:
        print("❌ Admin user has no collaboration team. Run load_test_data.py first.")
        sys.exit(1)

    start_time = time.time()
    print(f"⏱️  Starting schedule generation at {time.strftime('%H:%M:%S')}")

    try:
        schedules = BasicScheduleGenerator.generate(
            actor_email="admin@test.com",
            user=admin,
            team=active_team,
            random_seed=42,
        )

        elapsed = time.time() - start_time
        print(f"\n✅ SUCCESS! Schedule generated in {elapsed:.2f} seconds")
        print(f"   Created {len(schedules)} schedule assignments")

        # Group by group to see distribution
        from django.db.models import Count

        from schedule.models import Schedule

        by_group = (
            Schedule.objects.filter(created_by="admin@test.com", team=active_team)
            .values("group__name")
            .annotate(count=Count("id"))
            .order_by("group__name")
        )

        print("\n📊 Distribution by group:")
        for row in by_group:
            print(f"   • {row['group__name']}: {row['count']} assignments")

        print("\n📈 Performance Metrics:")
        print(f"   • Total sessions: {len(schedules)}")
        print(f"   • Total slots: {total_slots}")
        print(f"   • Time elapsed: {elapsed:.2f}s")
        print(f"   • Speed: {len(schedules) / elapsed:.1f} sessions/second")
        print(f"\n✨ Optimization achieved {60 / elapsed:.1f}x speedup vs 60s timeout!")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ FAILED after {elapsed:.2f} seconds")
        print(f"   Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    test_schedule_generation()
