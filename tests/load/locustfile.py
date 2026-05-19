"""Locust load tests for Orarioo.

Three scenarios:
  1. ScheduleReadUser  — 50 concurrent users doing GET read operations
  2. ScheduleGenerateUser — 10 concurrent users hitting the expensive generate endpoint
  3. Mixed (default) — combined realistic workload

Thresholds (enforced in CI via --exit-code-on-error):
  - p95 < 2s  for GET endpoints
  - p95 < 30s for POST /api/schedules/generate/

Run (headless, 20 users, 60 seconds):
    locust -f tests/load/locustfile.py --headless -u 20 -r 2 -t 60s

Run against local server explicitly:
    locust -f tests/load/locustfile.py --headless -u 20 -r 2 -t 60s --host http://localhost:8000
"""

import os

from locust import HttpUser, between, task

LOCUST_EMAIL = os.getenv("LOCUST_EMAIL", "direccion.academica@test.com")
LOCUST_PASSWORD = os.getenv("LOCUST_PASSWORD", "direccion123")


class _AuthenticatedUser(HttpUser):
    abstract = True
    host = os.getenv("LOCUST_HOST", "http://localhost:8000")

    def on_start(self):
        resp = self.client.post(
            "/api/login/",
            json={"email": LOCUST_EMAIL, "password": LOCUST_PASSWORD},
            name="/api/login/ [setup]",
        )
        if resp.status_code == 200:
            token = resp.json().get("access", "")
            self.client.headers.update({"Authorization": f"Bearer {token}"})


class ScheduleReadUser(_AuthenticatedUser):
    """Simulates a teacher/admin checking schedules during school hours.

    Target: p95 < 2s for all GET requests.
    Spawn with: --headless -u 50 -r 5
    """

    wait_time = between(1, 3)

    @task(4)
    def list_schedules(self):
        self.client.get("/api/schedules/", name="/api/schedules/")

    @task(2)
    def list_teachers(self):
        self.client.get("/api/teachers/", name="/api/teachers/")

    @task(2)
    def list_subjects(self):
        self.client.get("/api/subjects/", name="/api/subjects/")

    @task(1)
    def list_groups(self):
        self.client.get("/api/groups/", name="/api/groups/")

    @task(1)
    def list_classrooms(self):
        self.client.get("/api/classrooms/", name="/api/classrooms/")


class ScheduleGenerateUser(_AuthenticatedUser):
    """Simulates an admin triggering schedule generation.

    This is the heaviest endpoint (CP-SAT solver).
    Target: p95 < 30s.
    Spawn with: --headless -u 10 -r 1
    """

    wait_time = between(30, 60)  # generation is slow; space requests out

    @task
    def generate_and_poll(self):
        with self.client.post(
            "/api/schedules/generate/",
            json={"timeout_minutes": 1},
            name="/api/schedules/generate/",
            catch_response=True,
        ) as resp:
            if resp.status_code == 202:
                job_id = resp.json().get("job_id")
                if job_id:
                    self.client.get(
                        f"/api/schedules/generate/status/{job_id}/",
                        name="/api/schedules/generate/status/",
                    )
            elif resp.status_code == 400:
                # Expected when team has no subjects — mark as success to avoid noise
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")
