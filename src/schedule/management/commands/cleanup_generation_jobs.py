"""Management command to delete old ScheduleGenerationJob records."""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from schedule.models import ScheduleGenerationJob


class Command(BaseCommand):
    help = "Delete completed/errored ScheduleGenerationJob records older than N hours (default 24)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Delete jobs completed more than this many hours ago (default: 24).",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        if hours <= 0:
            raise CommandError("--hours must be a positive integer.")

        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        deleted, _ = ScheduleGenerationJob.objects.filter(
            status__in=[
                ScheduleGenerationJob.Status.DONE,
                ScheduleGenerationJob.Status.ERROR,
            ],
            completed_at__lt=cutoff,
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} generation job(s) older than {hours}h."
            )
        )
