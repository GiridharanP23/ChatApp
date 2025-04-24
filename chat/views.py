# views.py
from django.contrib.auth.models import User
from django.shortcuts import render
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tenant, Message, Group, Profile, Room
from .serializers import TenantSerializer, UserSerializer, GroupSerializer,MessageSerializer

class TenantRegisterView(APIView):
    def post(self, request):
        serializer = TenantSerializer(data=request.data)
        if serializer.is_valid():
            tenant = serializer.save()
            return Response({'id': tenant.id, 'name': tenant.name}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, tenant_id=None):
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                return Response({'error': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
            serializer = TenantSerializer(tenant)
            return Response(serializer.data)
        else:
            tenants = Tenant.objects.all()
            serializer = TenantSerializer(tenants, many=True)
            return Response(serializer.data)


# User Registration View (also creates tenant association)
class UserRegisterView(APIView):
    def post(self, request, *args, **kwargs):
        tenant_id = request.data.get('tenant_id')
        if not tenant_id:
            return Response({'error': 'tenant_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return Response({'error': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        # Exclude tenant_id from user serializer data
        user_data = {k: v for k, v in request.data.items() if k != 'tenant_id'}

        user_serializer = UserSerializer(data=user_data)
        if user_serializer.is_valid():
            user = user_serializer.save()
            Profile.objects.create(user=user, tenant=tenant)
        else:
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': 'User registered successfully',
            'tenant': tenant.name,
            'user': user.username
        }, status=status.HTTP_201_CREATED)


# Group Creation View
class GroupCreateView(APIView):
    def post(self, request):
        tenant_id = request.data.get('tenant_id')
        if not tenant_id:
            return Response({'error': 'tenant_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return Response({'error': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure tenant is included in validated data when saving
        request.data['tenant'] = tenant.id  # Manually add tenant ID to request data

        serializer = GroupSerializer(data=request.data)

        if serializer.is_valid():
            group = serializer.save()  # Tenant is automatically handled by serializer

            user_ids = request.data.get('members', [])
            users = User.objects.filter(id__in=user_ids)
            group.members.set(users)

            # Create and link the Room to the Group
            room = Room.objects.create(
                tenant=tenant,
                room_type='group',
                group=group,
                name=f"group_{tenant.id}_{group.id}"
            )
            room.participants.set(users)

            return Response({
                "id": group.id,
                "name": group.name,
                "tenant": tenant.id,
                "members": [user.id for user in group.members.all()],
                "room_id": room.id
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Pagination for Messages
class MessagePagination(PageNumberPagination):
    page_size = 5


# Chat Message History for Direct Messages
class ChatMessageHistoryAPIView(APIView):
    def get(self, request, tenant_id, user_1_id, user_2_id):
        try:
            # Ensure consistent room naming with tenant id
            room_name = f"dm_{tenant_id}_{min(user_1_id, user_2_id)}_{max(user_1_id, user_2_id)}"

            # Try to fetch the room by name and tenant
            room = Room.objects.filter(
                tenant_id=tenant_id,
                room_type='dm',
                name=room_name
            ).first()

            if not room:
                return Response(
                    {"detail": "No direct message room found for these users."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Retrieve messages for the room
            messages = Message.objects.filter(
                room=room
            ).order_by('-created_at')

            # Paginate and serialize
            paginator = MessagePagination()
            page = paginator.paginate_queryset(messages, request)
            serializer = MessageSerializer(page, many=True)

            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GroupChatHistoryAPIView(APIView):
    def get(self, request, tenant_id, group_id):
        try:
            # Retrieve the tenant and group based on provided IDs
            tenant = Tenant.objects.get(id=tenant_id)
            group = Group.objects.get(id=group_id, tenant=tenant)

            # Get the room associated with this group
            room = Room.objects.get(tenant=tenant, room_type='group', group=group)

            # Fetch messages in the group chat room
            messages = Message.objects.filter(room=room).order_by('-created_at')

            paginator = MessagePagination()
            page = paginator.paginate_queryset(messages, request)

            if page:
                serializer = MessageSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)

            # If there are no paginated results, send all messages
            serializer = MessageSerializer(messages, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except (Tenant.DoesNotExist, Group.DoesNotExist, Room.DoesNotExist):
            return Response({"detail": "Tenant, Group or Room not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)
