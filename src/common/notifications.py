import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _render_email_content(content):
    """Render email content from a raw string or a template descriptor."""
    if isinstance(content, dict):
        template_name = content.get("template")
        context = content.get("context") or {}
        if template_name:
            return render_to_string(template_name, context)
        return str(content.get("content", ""))

    if isinstance(content, (tuple, list)) and len(content) == 2:
        template_name, context = content
        if isinstance(template_name, str) and isinstance(context, dict):
            return render_to_string(template_name, context)

    return "" if content is None else str(content)


def send_security_email(subject, message, recipient_list, html_message=None):
    """Send a security notification email using Django's send_mail."""
    try:
        rendered_html = (
            _render_email_content(html_message) if html_message is not None else None
        )
        rendered_message = _render_email_content(message)
        if not rendered_message and rendered_html:
            rendered_message = strip_tags(rendered_html)

        sent_count = send_mail(
            subject=subject,
            message=rendered_message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=list(recipient_list),
            fail_silently=False,
            html_message=rendered_html,
        )
        return sent_count > 0
    except Exception:
        logger.exception(
            "Failed to send security email. subject=%s recipients=%s",
            subject,
            recipient_list,
        )
        return False
