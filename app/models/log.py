from tortoise import fields
from tortoise.models import Model


class Log(Model):
    id = fields.IntField(primary_key=True)
    message = fields.ForeignKeyField("models.Message", related_name="logs", null=True)
    action = fields.CharField(max_length=100)
    details = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "logs"

    def __repr__(self) -> str:
        return f"<Log {self.id} action={self.action}>"
