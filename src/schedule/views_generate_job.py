"""Background thread logic for async schedule generation jobs."""

import logging

from django.db import connection
from django.utils import timezone

from schedule.algorithm import BasicScheduleGenerator, ScheduleGenerationError
from schedule.models import ScheduleGenerationJob

logger = logging.getLogger(__name__)


def run_generation_job(
    *, job_id, actor_email, user_id, team_id, generation_seed, generation_options
):
    """Execute schedule generation in a background thread and persist the outcome.

    Stores only lightweight data in result_data (IDs + metadata).
    The generate_status endpoint re-queries and serializes with full request context.
    """
    connection.close()

    job = ScheduleGenerationJob.objects.get(id=job_id)
    job.status = ScheduleGenerationJob.Status.RUNNING
    job.current_phase = 1
    job.started_at = timezone.now()
    job.save(update_fields=["status", "current_phase", "started_at"])

    try:
        from django.contrib.auth import get_user_model

        from user.models import CollaborationTeam

        User = get_user_model()
        user = User.objects.get(id=user_id)
        active_team = CollaborationTeam.objects.get(id=team_id)

        def _on_phase2_start():
            ScheduleGenerationJob.objects.filter(id=job_id).update(current_phase=2)

        schedules, is_optimal, soft_score_info, tc_result = (
            BasicScheduleGenerator.generate(
                actor_email=actor_email,
                user=user,
                team=active_team,
                random_seed=generation_seed,
                generation_options=generation_options,
                on_phase2_start=_on_phase2_start,
            )
        )

        job.status = ScheduleGenerationJob.Status.DONE
        job.result_data = {
            "seed": generation_seed,
            "generation_options": generation_options,
            "optimization_is_optimal": is_optimal,
            "soft_score": soft_score_info,
            "schedule_ids": [s.id for s in schedules],
            "tc_warnings": tc_result.warnings if tc_result else [],
        }
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "result_data", "completed_at"])

    except ScheduleGenerationError as exc:
        logger.warning("Async generation failed: job=%s reason=%s", job_id, exc)
        job.status = ScheduleGenerationJob.Status.ERROR
        job.error_data = exc.to_response_data()
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_data", "completed_at"])

    except Exception:
        logger.exception("Unexpected error in generation job %s", job_id)
        job.status = ScheduleGenerationJob.Status.ERROR
        job.error_data = {
            "detail": "An unexpected error occurred during schedule generation.",
            "_error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected internal error occurred.",
            },
        }
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_data", "completed_at"])

    finally:
        connection.close()
