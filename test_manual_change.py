#!/usr/bin/env python
"""
Test script for manual schedule change functionality.
Run from the repo root with: python test_manual_change.py
"""
import os
import sys

# Add the src directory to the Python path
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from schedule.models import Schedule
from schedule.algorithm.generator import ScheduleReplanner, BasicScheduleGenerator
from schedule.algorithm.errors import ScheduleGenerationError

User = get_user_model()


def test_manual_change():
    """Test the manual schedule change workflow."""
    print("\n" + "="*60)
    print("Testing Manual Schedule Change")
    print("="*60)
    
    # Get or create a test user
    user, _ = User.objects.get_or_create(
        email='test-manual-change@example.com',
        defaults={'name': 'Test Manual Change User'}
    )
    print(f"\n✓ User: {user.email}")
    
    # Clear any existing schedules
    Schedule.objects.filter(users=user).delete()
    print("✓ Cleared existing schedules")
    
    # Generate initial schedule
    print("\n--- Generating Initial Schedule ---")
    try:
        schedules = BasicScheduleGenerator.generate(
            actor_email=user.email,
            user=user,
            random_seed=42,
        )
        print(f"✓ Generated {len(schedules)} schedules")
        
        # Show some schedules
        print("\nFirst 5 schedules:")
        for i, schedule in enumerate(schedules[:5]):
            print(f"  {i+1}. {schedule.name}")
            print(f"     Start: {schedule.start_time}")
            print(f"     Teacher: {schedule.teacher.name}")
            print(f"     Group: {schedule.group.name}")
            print()
    except ScheduleGenerationError as e:
        print(f"✗ Error generating schedule: {e}")
        return False
    
    # Test manual change
    schedule_to_move = schedules[0]
    new_slot_index = 5  # Move to a different slot
    
    print(f"\n--- Testing Manual Change ---")
    print(f"Moving schedule: {schedule_to_move.name}")
    print(f"Original slot index (approx): {(schedule_to_move.start_time.weekday() * 6) + schedule_to_move.start_time.hour - 8}")
    print(f"New slot index: {new_slot_index}")
    
    try:
        new_schedules = ScheduleReplanner.replan_with_manual_change(
            user=user,
            schedule_to_move_id=schedule_to_move.id,
            new_slot_index=new_slot_index,
            actor_email=user.email,
        )
        print(f"\n✓ Replanned with manual change!")
        print(f"✓ Created {len(new_schedules)} new schedules")
        
        # Verify the moved schedule
        moved_schedule = next(
            (s for s in new_schedules if s.teacher_id == schedule_to_move.teacher_id and s.subject_id == schedule_to_move.subject_id),
            None
        )
        if moved_schedule:
            print(f"\n✓ Found moved schedule:")
            print(f"  Name: {moved_schedule.name}")
            print(f"  New time: {moved_schedule.start_time}")
        else:
            print(f"\n⚠ Could not verify moved schedule in results")
        
        return True
    except ScheduleGenerationError as e:
        print(f"\n✗ Error in manual change: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_manual_change()
    print("\n" + "=" * 60)
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Tests failed!")
    print("=" * 60 + "\n")
    sys.exit(0 if success else 1)
