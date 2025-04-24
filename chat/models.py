from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User


class Tenant(models.Model):
    name = models.CharField(unique=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant):
        return self.get_queryset().for_tenant(tenant)


class TenantScopedModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    objects = TenantManager()

    class Meta:
        abstract = True


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, related_name='users', on_delete=models.CASCADE)

    def __str__(self):
        return f"Profile of {self.user.username}"


class Group(TenantScopedModel):
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(User, related_name='chat_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'name')

    def __str__(self):
        return f"Group {self.name} (Tenant {self.tenant.name})"


class Room(TenantScopedModel):
    ROOM_TYPE_CHOICES = (
        ('dm', 'Direct Message'),
        ('group', 'Group Chat'),
    )

    room_type = models.CharField(max_length=10, choices=ROOM_TYPE_CHOICES)
    participants = models.ManyToManyField(User, related_name='chat_rooms')
    group = models.OneToOneField(Group, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"{self.room_type.title()} Room {self.id}"

    def clean(self):
        if self.room_type == 'group' and not self.group:
            raise ValidationError("Group room must have a group assigned.")
        if self.room_type == 'dm' and self.group:
            raise ValidationError("Direct message room should not have a group assigned.")


class Message(TenantScopedModel):
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
