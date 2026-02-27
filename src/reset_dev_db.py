import os

import django
from django.db import connection

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")


def main() -> None:
    django.setup()

    with connection.cursor() as cursor:
        cursor.execute("DROP SCHEMA IF EXISTS public CASCADE;")
        cursor.execute("CREATE SCHEMA public;")

    print("Database schema reset completed.")


if __name__ == "__main__":
    main()
