from django.conf import settings
from django.db import models


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    category = models.CharField(max_length=40)
    title = models.CharField(max_length=180)
    body = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    dedupe_key = models.CharField(max_length=160, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["recipient", "dedupe_key"], name="uniq_notification_dedupe"),
        ]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return self.title
