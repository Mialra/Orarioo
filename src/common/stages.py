"""
Shared educational-stage definitions and normalization helpers.
"""

from django.db import models


class EducationalStage(models.TextChoices):
    """Canonical educational stage codes used across scheduling logic."""

    PRESCHOOL = "PRESCHOOL", "Infantil"
    PRIMARY = "PRIMARY", "Primaria"
    SECONDARY = "SECONDARY", "ESO"
    ALEVELS = "ALEVELS", "Bachillerato"


class GroupEducationalStage(models.TextChoices):
    """Educational stage values persisted by the group app."""

    PRESCHOOL = "preschool", EducationalStage.PRESCHOOL.label
    PRIMARY = "primary", EducationalStage.PRIMARY.label
    SECONDARY = "secondary", EducationalStage.SECONDARY.label
    ALEVELS = "alevels", EducationalStage.ALEVELS.label


GROUP_STAGE_TO_CANONICAL = {
    GroupEducationalStage.PRESCHOOL: EducationalStage.PRESCHOOL,
    GroupEducationalStage.PRIMARY: EducationalStage.PRIMARY,
    GroupEducationalStage.SECONDARY: EducationalStage.SECONDARY,
    GroupEducationalStage.ALEVELS: EducationalStage.ALEVELS,
}

STAGE_COLOR_CHOICES = (
    "red",
    "yellow",
    "orange",
    "green",
    "blue",
    "purple",
    "pink",
    "gray",
)

DEFAULT_STAGE_COLORS = {
    EducationalStage.PRESCHOOL: "green",
    EducationalStage.PRIMARY: "blue",
    EducationalStage.SECONDARY: "orange",
    EducationalStage.ALEVELS: "purple",
}


def canonical_group_stage(group_stage, default=EducationalStage.PRIMARY):
    """Return the canonical stage code for a group-stage value."""
    result = GROUP_STAGE_TO_CANONICAL.get(group_stage)
    if result is not None:
        return result
    if group_stage:
        return group_stage  # pass through custom code
    return default


def canonical_educational_stage(
    *,
    group_stage=None,
    default=EducationalStage.PRIMARY,
):
    """Resolve a canonical stage code from a group stage value."""
    if group_stage is not None:
        return canonical_group_stage(group_stage, default)
    return default
