from tortoise import fields
from tortoise.models import Model


class Contact(Model):
    id = fields.IntField(primary_key=True)
    external_id = fields.CharField(max_length=255, unique=True, index=True)
    phone = fields.CharField(max_length=30, null=True, index=True)
    email = fields.CharField(max_length=255, null=True, index=True)
    is_active = fields.BooleanField(default=True)
    name = fields.CharField(max_length=255, null=True)
    gender = fields.CharField(max_length=30, null=True)
    birth_date = fields.CharField(max_length=20, null=True)
    avatar_url = fields.CharField(max_length=500, null=True)
    profile_data = fields.JSONField(null=True)
    initial_analysis = fields.TextField(null=True)
    is_business = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "contacts"

    def __repr__(self) -> str:
        return f"<Contact {self.external_id}>"
