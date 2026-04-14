"""
Template context processors that inject shared data into every Django template.
"""

from app.constants import MAX_LENGTH_EXTENDED, STRING_MAX_LENGTH


def validation_constants(_request):
    """Inject validation length constants into every template context.
    Input: _request - Django HTTP request (unused, required by Django's processor protocol)
    Output: dict with string_max_length and max_length_extended keys
    """
    return {
        "string_max_length": STRING_MAX_LENGTH,
        "max_length_extended": MAX_LENGTH_EXTENDED,
    }
