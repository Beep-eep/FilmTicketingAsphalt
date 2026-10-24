"""Send Django email through Resend's HTTPS API (https://resend.com/docs/api-reference/emails/send-email).

Useful on hosts that block outgoing SMTP ports, such as Render's free web
services. Set RESEND_API_KEY and DEFAULT_FROM_EMAIL (an address on a domain
you verified in Resend; without a verified domain Resend only delivers to the
email address of your own Resend account).
"""
import logging

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            html = None
            for content, mimetype in getattr(message, "alternatives", []):
                if mimetype == "text/html":
                    html = content
            payload = {
                "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
                "to": list(message.to),
                "subject": message.subject,
                "text": message.body,
            }
            if html:
                payload["html"] = html
            if message.reply_to:
                payload["reply_to"] = list(message.reply_to)
            try:
                response = requests.post(
                    RESEND_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                    timeout=15,
                )
                if response.status_code >= 400:
                    raise RuntimeError(f"Resend returned {response.status_code}: {response.text[:300]}")
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
                log.exception("Resend email failed")
        return sent
