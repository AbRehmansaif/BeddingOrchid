from django.db import models
from django.urls import reverse
from apps.core.models import TimeStampedModel

class Page(TimeStampedModel):
    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    content = models.TextField(help_text='HTML/rich content for the policy or informational page')
    show_in_header = models.BooleanField(default=False)
    show_in_footer = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    # SEO
    seo_title = models.CharField(max_length=150, blank=True)
    seo_description = models.CharField(max_length=220, blank=True)

    class Meta:
        ordering = ['sort_order', 'title']

    def get_absolute_url(self):
        return reverse('pages:detail', kwargs={'slug': self.slug})

    def __str__(self):
        return self.title


class ContactMessage(TimeStampedModel):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    subject = models.CharField(max_length=150, default='General Inquiry')
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.subject}"
