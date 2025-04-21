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

    def __str__(self):
        return f"Profile of {self.user.username}"


class Group(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='groups', on_delete=models.CASCADE)
    name = models.CharField(unique=True, max_length=100)
    members = models.ManyToManyField(User, related_name='chat_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Group {self.name} (Tenant {self.tenant.name})"


class Room(models.Model):
    ROOM_TYPE_CHOICES = (
        ('dm', 'Direct Message'),
        ('group', 'Group Chat'),
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rooms')
    room_type = models.CharField(max_length=10, choices=ROOM_TYPE_CHOICES)
    participants = models.ManyToManyField(User, related_name='chat_rooms')
    group = models.OneToOneField(Group, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)  # Optional name
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"{self.room_type.title()} Room {self.id}"

    def clean(self):
        if self.room_type == 'group' and not self.group:
            raise ValidationError("Group room must have a group assigned.")
        if self.room_type == 'dm' and self.group:
            raise ValidationError("Direct message room should not have a group assigned.")


class Message(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='messages', on_delete=models.CASCADE)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    room = models.ForeignKey(Room, related_name='messages', on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['room', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
        ]

    def __str__(self):
        return f"Message from {self.sender.username} in {self.room.name if self.room else 'No Room'}"
