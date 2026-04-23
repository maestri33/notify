import pytest

from app.services.normalize import normalize_phone_sms, normalize_whatsapp_jid


class TestPhoneSms:
    def test_plus_country_code_formatted(self):
        assert normalize_phone_sms("+55 (43) 99664-8750") == "43996648750"

    def test_with_55(self):
        assert normalize_phone_sms("5543996648750") == "43996648750"

    def test_without_55(self):
        assert normalize_phone_sms("43996648750") == "43996648750"

    def test_legacy_10_digits_injects_9(self):
        assert normalize_phone_sms("4396648750") == "43996648750"

    def test_none(self):
        assert normalize_phone_sms(None) is None

    def test_empty(self):
        assert normalize_phone_sms("") is None

    def test_invalid_length(self):
        with pytest.raises(ValueError):
            normalize_phone_sms("123")


class TestWhatsappJid:
    def test_builds_jid(self):
        # Preserves digits as-is (13 with 9); Baileys decides via onWhatsApp()
        assert normalize_whatsapp_jid("+55 43 99664-8750") == "5543996648750@s.whatsapp.net"

    def test_without_country_code(self):
        assert normalize_whatsapp_jid("43996648750") == "5543996648750@s.whatsapp.net"

    def test_12_digits_legacy_no_9(self):
        # Older WA convention without the 9 — still valid input
        assert normalize_whatsapp_jid("554396648750") == "554396648750@s.whatsapp.net"

    def test_already_jid(self):
        assert (
            normalize_whatsapp_jid("554396648750@s.whatsapp.net")
            == "554396648750@s.whatsapp.net"
        )

    def test_none(self):
        assert normalize_whatsapp_jid(None) is None
