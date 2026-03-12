from datetime import datetime, time, timedelta

from django.utils import timezone


def build_weekly_slots():
    """Build one Monday-Friday timetable window with 6 hourly slots per day."""
    now = timezone.localtime()
    days_until_next_monday = (7 - now.weekday()) % 7
    if days_until_next_monday == 0:
        days_until_next_monday = 7

    start_day = now.date() + timedelta(days=days_until_next_monday)
    day_cursor = start_day
    slots = []

    morning_start_times = [
        time(hour=8, minute=30),
        time(hour=9, minute=30),
        time(hour=10, minute=30),
    ]
    afternoon_start_times = [
        time(hour=12, minute=0),
        time(hour=13, minute=0),
        time(hour=14, minute=0),
    ]

    for _ in range(5):
        for start_time_obj in morning_start_times:
            slots.append(
                timezone.make_aware(
                    datetime.combine(day_cursor, start_time_obj),
                    timezone.get_current_timezone(),
                )
            )
        for start_time_obj in afternoon_start_times:
            slots.append(
                timezone.make_aware(
                    datetime.combine(day_cursor, start_time_obj),
                    timezone.get_current_timezone(),
                )
            )
        day_cursor += timedelta(days=1)

    return slots


def build_slot_day_index(*, slots):
    """Map each slot index to its day index in the generated week."""
    day_index_by_slot = {}
    ordered_days = sorted({slot.date() for slot in slots})

    for day_idx, day in enumerate(ordered_days):
        for slot_idx, slot in enumerate(slots):
            if slot.date() == day:
                day_index_by_slot[slot_idx] = day_idx

    return day_index_by_slot
