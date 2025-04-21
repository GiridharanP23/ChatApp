from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User

class Tenant(models.Model):
    name = models.CharField(unique=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, related_name='users', on_delete=models.CASCADE)

class Group(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='groups', on_delete=models.CASCADE)
    name = models.CharField(unique=True,max_length=100)
    members = models.ManyToManyField(User, related_name='chat_groups')  # Changed the related_name here
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Group {self.name} (Tenant {self.tenant_id})"


class Message(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='messages', on_delete=models.CASCADE, null=True)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE, null=True)
    recipient = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE, null=True, blank=True)  # For direct messages only
    group = models.ForeignKey('Group', related_name='group_messages', on_delete=models.CASCADE, null=True, blank=True)  # For group messages only
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def is_group_message(self):
        return self.group is not None

    def is_direct_message(self):
        return self.recipient is not None and self.group is None

    def clean(self):
        if not self.group and not self.recipient:
            raise ValidationError("Message must have either a group or a recipient.")