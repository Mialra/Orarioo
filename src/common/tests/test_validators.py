"""Tests for common.validators.validators text and preference helpers.

Covers: validate_and_normalize_required_text, normalize_optional_text,
        validate_and_normalize_email, validate_case_insensitive_unique,
        normalize_time_preferences, validate_time_preferences.
Patterns: EP (valid/invalid input classes), BVA (exact length boundary), AAA.
Uses Django TestCase for DB-backed uniqueness tests; SimpleTestCase elsewhere.
"""

from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError

from common.validators.validators import (
    normalize_optional_text,
    normalize_time_preferences,
    validate_and_normalize_email,
    validate_and_normalize_required_text,
    validate_case_insensitive_unique,
    validate_time_preferences,
)
from teacher.models import Teacher
from user.models import CollaborationTeam


class ValidateAndNormalizeRequiredTextTest(SimpleTestCase):
    """EP: None, non-string, blank, too-long, valid. BVA: exact max_length."""

    def test_strips_surrounding_whitespace(self):
        """Leading and trailing whitespace must be stripped from the result."""
        result = validate_and_normalize_required_text("  hello  ", field_name="name")
        self.assertEqual(result, "hello", "Result must be stripped")

    def test_lowercase_flag_applied(self):
        """lowercase=True must convert the result to lowercase."""
        result = validate_and_normalize_required_text(
            "Hello World", field_name="name", lowercase=True
        )
        self.assertEqual(result, "hello world")

    def test_lowercase_false_preserves_case(self):
        """Default lowercase=False must preserve original case."""
        result = validate_and_normalize_required_text("Hello", field_name="name")
        self.assertEqual(result, "Hello")

    def test_none_raises_for_field(self):
        """None input must raise ValidationError targeting the named field."""
        with self.assertRaises(ValidationError) as ctx:
            validate_and_normalize_required_text(None, field_name="name")
        self.assertIn("name", ctx.exception.detail)

    def test_blank_string_raises(self):
        """A blank string (whitespace only) must raise ValidationError."""
        with self.assertRaises(ValidationError):
            validate_and_normalize_required_text("   ", field_name="name")

    def test_empty_string_raises(self):
        """An empty string must raise ValidationError."""
        with self.assertRaises(ValidationError):
            validate_and_normalize_required_text("", field_name="name")

    def test_non_string_raises(self):
        """A non-string value (int) must raise ValidationError."""
        with self.assertRaises(ValidationError):
            validate_and_normalize_required_text(123, field_name="name")

    def test_max_length_exact_passes(self):
        """BVA: a string of exactly max_length characters must pass."""
        result = validate_and_normalize_required_text(
            "ab", field_name="name", max_length=2
        )
        self.assertEqual(result, "ab")

    def test_max_length_exceeded_raises_for_field(self):
        """BVA: a string one character over max_length must raise for the field."""
        with self.assertRaises(ValidationError) as ctx:
            validate_and_normalize_required_text("abc", field_name="name", max_length=2)
        self.assertIn("name", ctx.exception.detail)

    def test_returns_string_type(self):
        """Return type must always be str."""
        result = validate_and_normalize_required_text("test", field_name="f")
        self.assertIsInstance(result, str)


class NormalizeOptionalTextTest(SimpleTestCase):
    """EP: None, empty string, whitespace, valid string, non-string."""

    def test_none_returns_empty_string(self):
        """None must be treated as absent and return ''."""
        self.assertEqual(normalize_optional_text(None, field_name="f"), "")

    def test_empty_string_returns_empty_string(self):
        """An empty string must return ''."""
        self.assertEqual(normalize_optional_text("", field_name="f"), "")

    def test_whitespace_only_returns_empty_string(self):
        """Whitespace-only input must normalize to ''."""
        self.assertEqual(normalize_optional_text("   ", field_name="f"), "")

    def test_valid_string_stripped(self):
        """A valid string must be stripped and returned."""
        self.assertEqual(normalize_optional_text("  hi  ", field_name="f"), "hi")

    def test_non_string_raises(self):
        """A non-string value must raise ValidationError."""
        with self.assertRaises(ValidationError):
            normalize_optional_text(42, field_name="f")

    def test_lowercase_flag_applied(self):
        """lowercase=True must lowercase the result."""
        result = normalize_optional_text("Hello", field_name="f", lowercase=True)
        self.assertEqual(result, "hello")


class ValidateAndNormalizeEmailTest(SimpleTestCase):
    """EP: valid email, invalid format, None, non-string. BVA: case normalization."""

    def test_valid_email_normalized(self):
        """A valid email with mixed case and whitespace must be lowercased and stripped."""
        result = validate_and_normalize_email("  Test@Example.COM  ")
        self.assertEqual(result, "test@example.com")

    def test_invalid_format_raises_for_field(self):
        """A string that is not a valid email must raise targeting the email field."""
        with self.assertRaises(ValidationError) as ctx:
            validate_and_normalize_email("notanemail", field_name="email")
        self.assertIn("email", ctx.exception.detail)

    def test_none_raises(self):
        """None input must raise ValidationError."""
        with self.assertRaises(ValidationError):
            validate_and_normalize_email(None)

    def test_empty_string_raises(self):
        """An empty string must raise ValidationError (blank required field)."""
        with self.assertRaises(ValidationError):
            validate_and_normalize_email("")

    def test_at_sign_only_raises(self):
        """'@' is not a valid email and must raise."""
        with self.assertRaises(ValidationError):
            validate_and_normalize_email("@")


class ValidateCaseInsensitiveUniqueTest(TestCase):
    """EP: duplicate (case-insensitive), unique value, update-self exclusion."""

    @classmethod
    def setUpTestData(cls):
        cls.team = CollaborationTeam.objects.create(name="Test Team Validators")
        cls.teacher = Teacher.objects.create(
            name="ExistingTeacher",
            max_weekly_hours=10,
            team=cls.team,
        )

    def _qs(self):
        return Teacher.objects.filter(team=self.team)

    def test_duplicate_case_insensitive_raises(self):
        """The same name in different case must raise ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            validate_case_insensitive_unique(
                "EXISTINGTEACHER", field_name="name", queryset=self._qs()
            )
        self.assertIn("name", ctx.exception.detail)

    def test_unique_value_returns_value(self):
        """A unique value must be returned unchanged."""
        result = validate_case_insensitive_unique(
            "NewTeacher", field_name="name", queryset=self._qs()
        )
        self.assertEqual(result, "NewTeacher")

    def test_same_instance_excluded_from_duplicate_check(self):
        """When updating the same instance, its own name must not trigger a duplicate error."""
        result = validate_case_insensitive_unique(
            "ExistingTeacher",
            field_name="name",
            queryset=self._qs(),
            instance=self.teacher,
        )
        self.assertEqual(result, "ExistingTeacher")

    def test_different_instance_same_name_raises(self):
        """A different instance with the same name must still raise."""
        other = Teacher(name="Other", max_weekly_hours=5, team=self.team)
        with self.assertRaises(ValidationError):
            validate_case_insensitive_unique(
                "existingteacher",
                field_name="name",
                queryset=self._qs(),
                instance=other,
            )


class NormalizeTimePreferencesTest(SimpleTestCase):
    """EP: None → {}, '' → {}, valid dict, non-dict."""

    def test_none_returns_empty_dict(self):
        self.assertEqual(normalize_time_preferences(None), {})

    def test_empty_string_returns_empty_dict(self):
        self.assertEqual(normalize_time_preferences(""), {})

    def test_valid_dict_returned_unchanged(self):
        prefs = {"MON_09:00": "AVAILABLE"}
        self.assertEqual(normalize_time_preferences(prefs), prefs)

    def test_non_dict_raises(self):
        """A non-dict, non-None value must raise ValidationError."""
        with self.assertRaises(ValidationError):
            normalize_time_preferences("not_a_dict")

    def test_list_raises(self):
        with self.assertRaises(ValidationError):
            normalize_time_preferences(["AVAILABLE"])


class ValidateTimePreferencesTest(SimpleTestCase):
    """EP: valid states, invalid state value, non-string key, empty/None input."""

    VALID_STATES = {"AVAILABLE", "PREFER_YES", "PREFER_NO", "UNAVAILABLE"}

    def test_none_returns_empty_dict(self):
        result = validate_time_preferences(None, valid_states=self.VALID_STATES)
        self.assertEqual(result, {})

    def test_valid_preferences_returned(self):
        prefs = {
            "MON_09:00": "PREFER_YES",
            "TUE_10:00": "UNAVAILABLE",
        }
        result = validate_time_preferences(prefs, valid_states=self.VALID_STATES)
        self.assertEqual(result, prefs)

    def test_invalid_state_value_raises_for_field(self):
        """A preference with an unrecognised state must raise targeting time_preferences."""
        prefs = {"MON_09:00": "INVALID_STATE"}
        with self.assertRaises(ValidationError) as ctx:
            validate_time_preferences(prefs, valid_states=self.VALID_STATES)
        self.assertIn("time_preferences", ctx.exception.detail)

    def test_non_string_key_raises(self):
        """A non-string key in the preferences dict must raise."""
        prefs = {123: "AVAILABLE"}
        with self.assertRaises(ValidationError):
            validate_time_preferences(prefs, valid_states=self.VALID_STATES)

    def test_non_dict_raises(self):
        """A non-dict value must raise."""
        with self.assertRaises(ValidationError):
            validate_time_preferences("not_a_dict", valid_states=self.VALID_STATES)

    def test_empty_dict_passes(self):
        """An explicitly empty dict must be valid."""
        result = validate_time_preferences({}, valid_states=self.VALID_STATES)
        self.assertEqual(result, {})
