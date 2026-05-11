"""
Management command that delegates to the top-level load_test_data script.
"""

from django.core.management.base import BaseCommand

from load_test_data import main as load_data_main


class Command(BaseCommand):
    """Django management command wrapper around the load_test_data script."""

    help = "Load test data using the existing load_test_data.py script."

    def handle(self, *args, **options):
        """Execute the load_test_data script and report progress to stdout.
        Input: args, options - standard management command arguments (unused)
        Output: None; writes NOTICE and SUCCESS messages to stdout as side effects
        """
        self.stdout.write(self.style.NOTICE("Running load_test_data..."))
        load_data_main()
        self.stdout.write(self.style.SUCCESS("load_test_data finished."))
