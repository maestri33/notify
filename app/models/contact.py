from tortoise import fields
from tortoise.models import Model


class Contact(Model):
    id = fields.IntField(primary_key=True)
    external_id = fields.CharField(max_length=255, unique=True, index=True)
    phone = fields.CharField(max_length=30, null=True, index=True)
    email = fields.CharField(max_length=255, null=True, index=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "contacts"

    def __repr__(self) -> str:
        return f"<Contact {self.external_id}>"
