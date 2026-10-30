from django.db import models
from apps.core.models import TimeStampedModel

class Redirect(TimeStampedModel):
    old_path = models.CharField(max_length=255, unique=True, db_index=True, help_text='e.g. /old-product-slug/')
    new_path = models.CharField(max_length=255, help_text='e.g. /products/new-product-slug/')
    is_301 = models.BooleanField(default=True, help_text='Permanent 301 redirect (recommended for SEO)')

    def __str__(self):
        return f"{self.old_path} -> {self.new_path} ({'301' if self.is_301 else '302'})"
