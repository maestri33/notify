import uuid

from app.models import Channel, Recipient
from app.services.router import eligible_channels


def _r(**kw) -> Recipient:
    return Recipient(
        id=uuid.uuid4(),
        external_id="x",
        **kw,
    )


def test_all_channels():
    r = _r(
        email="a@a.com",
        phone_sms="43996648750",
        whatsapp_jid="5543996648750@s.whatsapp.net",
        whatsapp_valid=True,
    )
    assert set(eligible_channels(r)) == {Channel.whatsapp, Channel.sms, Channel.email}


def test_whatsapp_invalid_excluded():
    r = _r(whatsapp_jid="5543996648750@s.whatsapp.net", whatsapp_valid=False, email="a@a.com")
    assert eligible_channels(r) == [Channel.email]


def test_no_data():
    assert eligible_channels(_r()) == []


def test_forced_intersection():
    r = _r(email="a@a.com", phone_sms="43996648750")
    assert eligible_channels(r, forced=[Channel.whatsapp, Channel.email]) == [Channel.email]


def test_forced_empty_result():
    r = _r(email="a@a.com")
    assert eligible_channels(r, forced=[Channel.whatsapp]) == []
