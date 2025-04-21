from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Tenant, Group, Message


# Serializer for Tenant model
class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'created_at']

# Serializer for User model
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email', 'first_name', 'last_name']

    def create(self, validated_data):
        # Create a new user with hashed password
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            password=validated_data['password']
        )
        return user
# chat/serializers.py


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name', 'tenant', 'members']  # Keep 'members' in the fields for validation, but not for creation

    def create(self, validated_data):
        # Remove members from validated_data
        members = validated_data.pop('members', [])

        # Create the group without members
        group = Group.objects.create(**validated_data)

        # Add members using set() after creating the group
        group.members.set(members)

        return group

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['sender', 'content', 'created_at']


