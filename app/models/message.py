from tortoise import fields
from tortoise.models import Model


class Message(Model):
    id = fields.IntField(primary_key=True)
    contact = fields.ForeignKeyField("models.Contact", related_name="messages")
    type = fields.CharField(max_length=20)  # text, audio, media
    content_text = fields.TextField(null=True)
    whatsapp_status = fields.CharField(max_length=20, default="pending")
    email_status = fields.CharField(max_length=20, default="pending")
    email_subject = fields.CharField(max_length=255, null=True)
    tts_audio_url = fields.CharField(max_length=500, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "messages"

    def __repr__(self) -> str:
        return f"<Message {self.id} type={self.type}>"
