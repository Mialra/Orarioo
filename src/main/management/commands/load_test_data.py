from django.core.management.base import BaseCommand

from load_test_data import main as load_data_main


class Command(BaseCommand):
    help = "Load test data using the existing load_test_data.py script."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Running load_test_data..."))
        load_data_main()
        self.stdout.write(self.style.SUCCESS("load_test_data finished."))
