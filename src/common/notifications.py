"""
Email notification utilities for sending security and transactional emails.
Uses Django's send_mail with optional HTML template rendering via django.template.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _render_email_content(content):
    """Render email content from a raw string or a template descriptor dict.
    Input: content - str, None, or dict with optional 'template'/'context'/'content' keys
    Output: rendered string (HTML or plain text); empty string for None input
    """
    if isinstance(content, dict):
        template_name = content.get("template")
        context = content.get("context") or {}
        if template_name:
            return render_to_string(template_name, context)
        return str(content.get("content", ""))

    return "" if content is None else str(content)


def send_security_email(subject, message, recipient_list, html_message=None):
    """Send a security notification email, rendering templates when needed.
    Input: subject - email subject string; message - plain-text body or descriptor; recipient_list - list of recipient addresses; html_message - optional HTML body or descriptor dict
    Output: True if at least one email was accepted by the mail server, False on any failure
    """
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
