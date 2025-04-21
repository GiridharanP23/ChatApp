# views.py
from django.contrib.auth.models import User
from django.shortcuts import render
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tenant, Message, Group
from .serializers import TenantSerializer, UserSerializer, GroupSerializer,MessageSerializer


class TenantRegisterView(APIView):
    def post(self, request):
        serializer = TenantSerializer(data=request.data)
        if serializer.is_valid():
            tenant = serializer.save()
            return Response({'id': tenant.id, 'name': tenant.name}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # GET method to retrieve tenant details by id
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


# View to register a new user and associate them with a tenant
class UserRegisterView(APIView):
    def post(self, request, *args, **kwargs):
        # Get tenant data from the request payload
        tenant_data = request.data.get('tenant')

        # Validate and save the tenant data
        tenant_serializer = TenantSerializer(data=tenant_data)
        if tenant_serializer.is_valid():
            tenant = tenant_serializer.save()
        else:
            return Response(tenant_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get user data from the request payload
        user_data = request.data.get('user')

        # Validate and save the user data
        user_serializer = UserSerializer(data=user_data)
        if user_serializer.is_valid():
            user = user_serializer.save()
            # Optionally associate the user with the tenant
            user.tenant = tenant
            user.save()
        else:
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Return a success response
        return Response({
            'message': 'User registered successfully',
            'tenant': tenant.name,
            'user': user.username
        }, status=status.HTTP_201_CREATED)

class GroupCreateView(APIView):
    def post(self, request):
        # Deserialize the incoming data
        serializer = GroupSerializer(data=request.data)

        if serializer.is_valid():
            # Create the group first
            group = serializer.save()

            # Now, handle adding members to the group
            user_ids = request.data.get('members', [])
            users = User.objects.filter(id__in=user_ids)

            # Set the members for the group using the 'set()' method
            group.members.set(users)

            # Return the group details in the response
            return Response({
                "id": group.id,
                "name": group.name,
                "tenant": group.tenant.id,
                "members": [user.id for user in group.members.all()]
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MessagePagination(PageNumberPagination):
    page_size = 5


class ChatMessageHistoryAPIView(APIView):
    def get(self, request, tenant_id, user_1_id, user_2_id):
        try:
            # Fetch messages between the two users (either direct or group messages)
            messages = Message.objects.filter(
                tenant_id=tenant_id,
                # For direct messages
                recipient_id__in=[user_1_id, user_2_id],
                sender_id__in=[user_1_id, user_2_id]
            ).order_by('-created_at')

            # Add group message filtering (messages in groups that include the users)
            group_messages = Message.objects.filter(
                tenant_id=tenant_id,
                group__members__in=[user_1_id, user_2_id]
            ).order_by('-created_at')

            # Combine both sets of messages and remove duplicates (if any)
            messages = messages | group_messages  # Union of both querysets
            messages = messages.distinct()  # Remove duplicates if any exist

            # Handle pagination
            paginator = MessagePagination()
            page = paginator.paginate_queryset(messages, request)
            serializer = MessageSerializer(page, many=True)

            # Return the paginated response
            return paginator.get_paginated_response(serializer.data)

        except Message.DoesNotExist:
            # Return a 404 if no messages are found for the given users
            return Response({"detail": "Messages not found."}, status=404)
        except Exception as e:
            # Handle any unexpected errors
            return Response({"detail": str(e)}, status=500)


class GroupChatHistoryAPIView(APIView):
    def get(self, request, tenant_id, group_id):
        try:
            # Retrieve the tenant and group based on provided IDs
            tenant = Tenant.objects.get(id=tenant_id)
            group = Group.objects.get(id=group_id, tenant=tenant)
        except (Tenant.DoesNotExist, Group.DoesNotExist):
            return Response({"detail": "Tenant or Group not found."}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve all messages for this group, ordered by creation time (newest first)
        messages = Message.objects.filter(group=group).order_by('-created_at')

        # Handle pagination
        paginator = MessagePagination()
        page = paginator.paginate_queryset(messages, request)

        if page:
            serializer = MessageSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        # If no pagination is needed, return all messages
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
