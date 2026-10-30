from django.db import models
from apps.core.models import TimeStampedModel

class MetaEventLog(TimeStampedModel):
    event_name = models.CharField(max_length=50)
    event_id = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField(default=dict)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    is_success = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event_name} ({self.event_id}) - {'OK' if self.is_success else 'FAILED'}"
