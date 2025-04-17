
from django.db import models
from django.contrib.auth.models import User

class Tenant(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Group(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='groups', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(User, related_name='groups')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Group {self.name} (Tenant {self.tenant_id})"


class Message(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='messages', on_delete=models.CASCADE)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    content = models.TextField()  # Content of the message
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp of when the message was created

    # Optional: For group messages
    group = models.ForeignKey('Group', related_name='messages', on_delete=models.CASCADE, null=True, blank=True)

    # For Direct Messages (we can use user pairs as a simple filter)
    user_1 = models.ForeignKey(User, related_name='received_messages_1', on_delete=models.CASCADE, null=True, blank=True)
    user_2 = models.ForeignKey(User, related_name='received_messages_2', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.content

    @property
    def is_group_message(self):
        return self.group is not None

    @property
    def is_direct_message(self):
        return self.user_1 is not None and self.user_2 is not None

