"""
Shared educational-stage definitions and normalization helpers.
"""

from django.db import models


class EducationalStage(models.TextChoices):
    """Canonical educational stage codes used across scheduling logic."""

    PRESCHOOL = "PRESCHOOL", "Preschool"
    PRIMARY = "PRIMARY", "Primary"
    SECONDARY = "SECONDARY", "Secondary"


class GroupEducationalStage(models.TextChoices):
    """Educational stage values persisted by the group app."""

    PRESCHOOL = "preschool", EducationalStage.PRESCHOOL.label
    PRIMARY = "primary", EducationalStage.PRIMARY.label
    SECONDARY = "secondary", EducationalStage.SECONDARY.label


GROUP_STAGE_TO_CANONICAL = {
    GroupEducationalStage.PRESCHOOL: EducationalStage.PRESCHOOL,
    GroupEducationalStage.PRIMARY: EducationalStage.PRIMARY,
    GroupEducationalStage.SECONDARY: EducationalStage.SECONDARY,
}

SUBJECT_STAGE_TO_CANONICAL = {
    EducationalStage.PRESCHOOL: EducationalStage.PRESCHOOL,
    EducationalStage.PRIMARY: EducationalStage.PRIMARY,
    EducationalStage.SECONDARY: EducationalStage.SECONDARY,
}


def canonical_group_stage(group_stage, default=EducationalStage.PRIMARY):
    """Return the canonical stage code for a group-stage value."""
    return GROUP_STAGE_TO_CANONICAL.get(group_stage, default)


def canonical_subject_stage(subject_stage, default=EducationalStage.PRIMARY):
    """Return the canonical stage code for a subject-stage value."""
    return SUBJECT_STAGE_TO_CANONICAL.get(subject_stage, default)


def canonical_educational_stage(
    *,
    group_stage=None,
    subject_stage=None,
    default=EducationalStage.PRIMARY,
):
    """Resolve a canonical stage code from a group or subject stage value."""
    if group_stage is not None:
        return canonical_group_stage(group_stage, default)
    if subject_stage is not None:
        return canonical_subject_stage(subject_stage, default)
    return default
