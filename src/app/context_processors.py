from app.constants import STRING_MAX_LENGTH, MAX_LENGTH_EXTENDED


def validation_constants(request):
    """
    Inject validation constants into every template context.
    This makes them available as {{ string_max_length }} and {{ max_length_extended }}
    in all templates, and as window.ValidationConstants in JavaScript.
    """
    return {
        "string_max_length": STRING_MAX_LENGTH,
        "max_length_extended": MAX_LENGTH_EXTENDED,
    }
