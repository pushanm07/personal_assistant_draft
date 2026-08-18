"""Email actions for ALANA — SMTP over Gmail with a hard, code-enforced allowlist.

Only the three trusted recipient addresses below (and their friendly aliases)
can ever receive an email. This is enforced *here in code* at two points —
``resolve_recipient()``/``is_trusted_recipient()`` and again inside
``send_email()`` right before any network connection is made — never by the
LLM, so a confused interpretation can never exfiltrate an email to a stranger.

Sending always passes through a confirmation layer:
  - ``confirm=True`` (default): the caller is prompted before connecting.
  - ``confirm=False``: used by the desktop UI *after* the user confirmed in
    its own confirmation dialog, so the console is never blocked.
"""

from __future__ import annotations

import os
import re
import smtplib
from email.message import EmailMessage

# --------------------------------------------------------------------------- #
# Account + credentials
# --------------------------------------------------------------------------- #
EMAIL_ADDRESS = "baleshisballistic@gmail.com"
# Gmail app password. The value below is the current placeholder; set the
# EMAIL_APP_PASSWORD environment variable to override it without editing code.
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "ngse myuk vpnk pnao")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_TIMEOUT = 20.0

# --------------------------------------------------------------------------- #
# Trusted recipients ONLY — enforced below, never by the model.
# --------------------------------------------------------------------------- #
TRUSTED_RECIPIENTS = frozenset(
    {
        "chinmayshyamsundar@gmail.com",
        "pushanmukherjee07@gmail.com",
        "abhinavpalanivel@gmail.com",
    }
)

# Friendly aliases that resolve onto the trusted addresses. Full addresses are
# also accepted and checked against the allowlist directly.
_RECIPIENT_ALIASES = {
    "chinmay": "chinmayshyamsundar@gmail.com",
    "chinmayshyamsundar": "chinmayshyamsundar@gmail.com",
    "chinmayshyamsundar@gmail.com": "chinmayshyamsundar@gmail.com",
    "pushan": "pushanmukherjee07@gmail.com",
    "pushanmukherjee07": "pushanmukherjee07@gmail.com",
    "pushanmukherjee07@gmail.com": "pushanmukherjee07@gmail.com",
    "abhinav": "abhinavpalanivel@gmail.com",
    "abhinavpalanivel": "abhinavpalanivel@gmail.com",
    "abhinavpalanivel@gmail.com": "abhinavpalanivel@gmail.com",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def resolve_recipient(recipient: str) -> str | None:
    """Return the canonical *allowed* email for *recipient*, or None.

    ``None`` means the recipient is NOT on the trust list and must be refused.
    """
    key = (recipient or "").strip().lower()
    if not key:
        return None
    direct = _RECIPIENT_ALIASES.get(key)
    if direct is not None:
        return direct
    # Bare addresses resolve straight against the allowlist.
    if _EMAIL_RE.match(key) and key in TRUSTED_RECIPIENTS:
        return key
    return None


def is_trusted_recipient(recipient: str) -> bool:
    """True when *recipient* resolves onto the trusted allowlist."""
    return resolve_recipient(recipient) is not None


def trusted_aliases() -> tuple[str, ...]:
    """Return every accepted alias/address (for heuristics like intent parsing)."""
    return tuple(sorted(set(_RECIPIENT_ALIASES) | TRUSTED_RECIPIENTS))


def _confirm_send(recipient_email: str, subject: str, print_fn) -> bool:
    """Console confirmation layer. True only on an explicit 'yes'."""
    print_fn("\n[ALANA · EMAIL CONFIRMATION]")
    print_fn(f"  To:      {recipient_email}")
    print_fn(f"  Subject: {subject or '(none)'}")
    try:
        answer = input("Send this email? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def send_email(
    recipient: str,
    subject: str = "",
    body: str = "",
    *,
    confirm: bool = True,
    print_fn=print,
    input_fn=input,
) -> bool:
    """Send *body* to *recipient* via Gmail SMTP.

    Returns True on success. Refuses (returns False) when the recipient is not
    on the trust list — enforced here regardless of any confirmation step.
    """
    recipient_email = resolve_recipient(recipient)
    if recipient_email is None:
        print_fn(
            f"REFUSED: '{recipient}' is not on ALANA's trusted recipient list. "
            "No email was sent."
        )
        return False

    if confirm:
        if not _confirm_send(recipient_email, subject, print_fn):
            print_fn("Email cancelled.")
            return False

    message = EmailMessage()
    message["From"] = EMAIL_ADDRESS
    message["To"] = recipient_email
    message["Subject"] = (subject or "").strip() or "Message from ALANA"
    message.set_content((body or "").strip() or " ")

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - network/provider dependent
        print_fn(f"Email failed to send: {exc}")
        return False

    print_fn(f"Email sent to {recipient_email}.")
    return True


def send_email_command(recipient: str, message: str) -> bool:
    """Action-registry entry point used by Brain's ``send_email`` action.

    The console confirmation layer is active here (``confirm=True``); the
    desktop UI replaces this with its own GUI confirmation via
    ``InProcessClient.set_email_confirmation``.
    """
    return send_email(
        recipient,
        subject="Message from ALANA",
        body=message,
        confirm=True,
    )
