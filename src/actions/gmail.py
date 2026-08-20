"""Gmail actions for ALANA."""

from __future__ import annotations

from services.gmail import create_draft, list_recent, reply_to_message, send_message


def read_email(query: str = "newer_than:30d", limit: int = 5) -> str:
    """Return a concise inbox digest from cleaned Gmail messages."""
    messages = list_recent(query=query, limit=limit)
    if not messages:
        return "There are no matching emails, Sir."
    lines = []
    for message in messages:
        sender = message["from"] or "unknown sender"
        subject = message["subject"] or "(no subject)"
        preview = message["body"] or message["snippet"]
        lines.append(f"{subject} from {sender}. {preview[:240]}")
    return "\n".join(lines)


def draft_email(recipient: str, subject: str, body: str) -> str:
    """Create a Gmail draft without sending it."""
    draft_id = create_draft(recipient, subject, body)
    return f"Drafted the email to {recipient}, Sir."


def send_email_with_confirmation(
    recipient: str,
    subject: str,
    body: str,
    confirm,
) -> str:
    """Send through Gmail API only after the caller explicitly confirms."""
    if not confirm({"recipient": recipient, "subject": subject, "body": body}):
        return "Email cancelled, Sir."
    send_message(recipient, subject, body)
    return f"Email sent to {recipient}, Sir."


def reply_email(message_id: str, body: str) -> str:
    """Reply to a Gmail message by id."""
    reply_to_message(message_id, body)
    return "Reply sent, Sir."
