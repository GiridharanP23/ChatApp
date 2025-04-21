import json
import logging
from urllib.parse import parse_qs
import os
import django
from channels.db import database_sync_to_async
from django.core.paginator import Paginator
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Whatsapp1.settings')
django.setup()
import redis
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

from chat.models import Tenant, Message, Group

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
active_users = {}
logger = logging.getLogger(__name__)

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)
MESSAGES_PER_PAGE = 20


class DMConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        self.user_1_id = int(self.scope['url_route']['kwargs']['user_1_id'])
        self.user_2_id = int(self.scope['url_route']['kwargs']['user_2_id'])

        query_string = self.scope['query_string'].decode()
        query_params = parse_qs(query_string)  # Parsing the query string

        user_id = query_params.get('user_id', [None])[0]
        if not user_id:
            await self.close()
            return

        self.user_id = int(user_id)

        # Ensure the user is one of the participants in the direct message
        if self.user_id not in {self.user_1_id, self.user_2_id}:
            await self.close()
            return

        self.room_name = f'dm_{self.tenant_id}_{self.user_1_id}_{self.user_2_id}'

        await self.accept()  # Accept the WebSocket connection before sending any data
        await self.channel_layer.group_add(self.room_name, self.channel_name)

        # Fetch and send existing messages
        messages = await self.fetch_messages(page_number=1)
        await self.send(text_data=json.dumps({'messages': messages}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        # Handle pagination request
        if 'request_more' in data:  # Handling request for more messages (pagination)
            current_page = data.get('page_number', 1)
            next_page = current_page + 1
            messages = await self.fetch_messages(page_number=next_page)
            await self.send(text_data=json.dumps({'messages': messages}))

        # Handle sending a message
        message = data.get('message')
        if message:
            # Save the message and broadcast it to the WebSocket group
            await self.save_message(
                tenant_id=self.tenant_id,
                sender_id=self.user_id,
                content=message,
                recipient_id=self.user_1_id if self.user_id != self.user_1_id else self.user_2_id
            )
            await self.channel_layer.group_send(
                self.room_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'user': self.user_id
                }
            )

    async def chat_message(self, event):
        # Send the received chat message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'user': event['user']
        }))

    async def fetch_messages(self, page_number=1):
        return await self.get_paginated_serialized_messages(page_number)

    @database_sync_to_async
    def get_paginated_serialized_messages(self, page_number):
        # Filter messages between the two users (direct messages only)
        messages = Message.objects.filter(
            tenant_id=self.tenant_id,
            sender_id__in=[self.user_1_id, self.user_2_id],
            recipient_id__in=[self.user_1_id, self.user_2_id]
        ).order_by('-created_at')

        paginator = Paginator(messages, 20)  # Assuming you want 20 messages per page
        page = paginator.get_page(page_number)

        return [
            {
                'sender': message.sender.username,
                'content': message.content,
                'timestamp': str(message.created_at),
            }
            for message in page.object_list
        ]

    @database_sync_to_async
    def save_message(self, tenant_id, sender_id, content, recipient_id):
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            sender = User.objects.get(id=sender_id)
            recipient = User.objects.get(id=recipient_id)

            # Create a new direct message and save it to the database
            Message.objects.create(
                tenant=tenant,
                sender=sender,
                content=content,
                group=None,  # No group for direct messages
                recipient=recipient
            )
        except (Tenant.DoesNotExist, User.DoesNotExist) as e:
            # Log or handle the exception
            print(f"Error: {e}")
            pass


class GroupConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        self.group_id = int(self.scope['url_route']['kwargs']['group_id'])

        # Parse the query parameters for user_id
        query_string = self.scope['query_string'].decode()
        query_params = parse_qs(query_string)
        user_id = query_params.get('user_id', [None])[0]

        if not user_id:
            await self.close()
            return

        self.user_id = int(user_id)

        # Fetch the group and check if the user is a member
        self.group = await self.get_group()
        if not self.group or not await self.is_user_member(self.user_id):
            await self.close()
            return

        # Define the room name
        self.room_name = f'group_{self.tenant_id}_{self.group_id}'

        # Accept the WebSocket connection
        await self.accept()
        await self.channel_layer.group_add(self.room_name, self.channel_name)

        # Send the initial set of messages to the user
        messages = await self.fetch_messages(page_number=1)
        await self.send(text_data=json.dumps({'messages': messages}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        # Handling request for more messages (pagination)
        if 'request_more' in data:
            current_page = data.get('page_number', 1)
            next_page = current_page + 1
            messages = await self.fetch_messages(page_number=next_page)
            await self.send(text_data=json.dumps({'messages': messages}))

        # Handle sending messages
        message = data.get('message')
        if message:
            # Save the message and broadcast it to the group
            await self.save_message(
                tenant_id=self.tenant_id,
                sender_id=self.user_id,
                content=message,
                group_id=self.group_id
            )
            await self.channel_layer.group_send(
                self.room_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'user': self.user_id
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'user': event['user']
        }))

    async def fetch_messages(self, page_number=1):
        return await self.get_paginated_serialized_messages(page_number)

    @database_sync_to_async
    def get_paginated_serialized_messages(self, page_number):
        # Fetch messages related to the group
        messages = Message.objects.filter(
            tenant_id=self.tenant_id,
            group_id=self.group_id
        ).order_by('-created_at')

        paginator = Paginator(messages, MESSAGES_PER_PAGE)
        page = paginator.get_page(page_number)

        return [
            {
                'sender': message.sender.username,
                'content': message.content,
                'timestamp': str(message.created_at),
            }
            for message in page.object_list
        ]

    @database_sync_to_async
    def get_group(self):
        # Fetch the group using tenant_id and group_id
        try:
            return Group.objects.get(id=self.group_id, tenant_id=self.tenant_id)
        except Group.DoesNotExist:
            return None

    @database_sync_to_async
    def is_user_member(self, user_id):
        # Efficient check for user membership in the group
        return self.group.members.filter(id=user_id).exists()

    @database_sync_to_async
    def save_message(self, tenant_id, sender_id, content, group_id):
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            sender = User.objects.get(id=sender_id)
            group = Group.objects.get(id=group_id)

            # Create and save the new message
            Message.objects.create(
                tenant=tenant,
                sender=sender,
                content=content,
                group=group,  # Assign message to the group
            )
        except (Tenant.DoesNotExist, User.DoesNotExist, Group.DoesNotExist) as e:
            # Log or handle the exception
            print(f"Error saving message: {e}")
