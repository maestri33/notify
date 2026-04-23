"""Determine which channels should receive a given notification."""

from app.models import Channel, Recipient


def eligible_channels(
    recipient: Recipient, forced: list[Channel] | None = None
) -> list[Channel]:
    """Return channels that have registered data on this recipient.

    Rules (from spec §5):
    - whatsapp requires both a JID and whatsapp_valid=True
    - sms requires phone_sms
    - email requires email
    - if `forced` is provided, result is the intersection with available
    - no fallback between channels; each is independent
    """
    available: list[Channel] = []
    if recipient.whatsapp_jid and recipient.whatsapp_valid:
        available.append(Channel.whatsapp)
    if recipient.phone_sms:
        available.append(Channel.sms)
    if recipient.email:
        available.append(Channel.email)

    if forced is None:
        return available
    return [c for c in available if c in forced]
