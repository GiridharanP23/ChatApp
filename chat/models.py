
from django.db import models
from django.contrib.auth.models import User

class Tenant(models.Model):
    name = models.CharField(max_length=255)
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
    tenant = models.ForeignKey(Tenant, related_name='messages', on_delete=models.CASCADE,null=True)  # Added tenant field
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE,null=True)
    content = models.TextField()  # Message content
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp
    is_read = models.BooleanField(default=False)  # Read status

    # Fields for Direct Messages
    user_1 = models.ForeignKey(User, related_name='received_messages_1', on_delete=models.CASCADE, null=True, blank=True)
    user_2 = models.ForeignKey(User, related_name='received_messages_2', on_delete=models.CASCADE, null=True, blank=True)

    # Fields for Group Messages
    group = models.ForeignKey('Group', related_name='group_messages', on_delete=models.CASCADE, null=True, blank=True)

    def is_group_message(self):
        return self.group is not None

    def is_direct_message(self):
        return self.user_1 is not None and self.user_2 is not None

