"""Schedule generation algorithm package (CP-SAT based)."""

from schedule.algorithm.errors import ScheduleGenerationError
from schedule.algorithm.generator import BasicScheduleGenerator

__all__ = ["BasicScheduleGenerator", "ScheduleGenerationError"]
