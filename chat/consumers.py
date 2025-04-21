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
        try:
            self.user_id = int(query_string.split('=')[-1])
        except ValueError:
            await self.close()
            return

        if self.user_id not in {self.user_1_id, self.user_2_id}:
            await self.close()
            return

        self.room_name = f'dm_{self.tenant_id}_{self.user_1_id}_{self.user_2_id}'

        await self.accept()  # Move this here — accept the WebSocket before sending anything

        await self.channel_layer.group_add(self.room_name, self.channel_name)

        messages = await self.fetch_messages(page_number=1)
        await self.send(text_data=json.dumps({'messages': messages}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        if 'request_more' in data:  # Handling request for more messages (pagination)
            current_page = data.get('page_number', 1)
            next_page = current_page + 1
            messages = await self.fetch_messages(page_number=next_page)
            await self.send(text_data=json.dumps({'messages': messages}))

        # Handle sending messages
        message = data.get('message')
        if message:
            # Save the message and broadcast it
            await self.save_message(
                tenant_id=self.tenant_id,
                sender_id=self.user_id,
                content=message,
                user_1_id=self.user_1_id,
                user_2_id=self.user_2_id
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
        messages = Message.objects.filter(
            tenant_id=self.tenant_id,
            user_1_id=self.user_1_id,
            user_2_id=self.user_2_id
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
    def get_messages(self):
        return Message.objects.filter(
            tenant_id=self.tenant_id,
            user_1_id=self.user_1_id,
            user_2_id=self.user_2_id
        ).order_by('-created_at')

    @database_sync_to_async
    def get_page(self, paginator, page_number):
        # Sync-to-async for page fetching
        page = paginator.get_page(page_number)
        return page

    @sync_to_async
    def save_message(self, tenant_id, sender_id, content, user_1_id, user_2_id):
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            sender = User.objects.get(id=sender_id)
            user_1 = User.objects.get(id=user_1_id)
            user_2 = User.objects.get(id=user_2_id)

            # Create a new message and save it to the database
            Message.objects.create(
                tenant=tenant,
                sender=sender,
                content=content,
                group=None,
                user_1=user_1,
                user_2=user_2
            )
        except (Tenant.DoesNotExist, User.DoesNotExist) as e:
            # Log or handle the exception
            print(f"Error: {e}")
            pass


class GroupConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']  # Get tenant_id from URL
        self.group_id = self.scope['url_route']['kwargs']['group_id']  # Get group_id from URL
        self.user_id = self.scope['query_string'].decode().split('=')[1]  # Extract user_id from query parameter

        # Check if the user is part of the group
        if not await self.is_user_in_group(self.user_id, self.group_id):
            await self.close()  # Close the WebSocket if user is not part of the group
            return

        self.room_name = f'tenant_{self.tenant_id}_group_{self.group_id}'  # Include tenant_id in room name
        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message', '')

        # Save to DB
        await self.save_group_message(self.tenant_id, self.user_id, self.group_id, message)

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

    @database_sync_to_async
    def is_user_in_group(self, user_id, group_id):
        try:
            group = Group.objects.get(id=group_id)
            user = User.objects.get(id=user_id)
            return user in group.members.all()  # Check if user is a member of the group
        except (Group.DoesNotExist, User.DoesNotExist):
            return False

    @database_sync_to_async
    def save_group_message(self, tenant_id, sender_id, group_id, content):
        tenant = Tenant.objects.get(id=tenant_id)
        sender = User.objects.get(id=sender_id)
        group = Group.objects.get(id=group_id)

        Message.objects.create(
            tenant=tenant,
            sender=sender,
            group=group,
            content=content
        )
