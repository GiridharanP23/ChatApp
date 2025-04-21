import json
import logging
from urllib.parse import parse_qs
import os
import django
from channels.db import database_sync_to_async
from django.core.paginator import Paginator
from django.utils import timezone

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


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']

        # Extract the user_id from the query parameters
        query_string = self.scope['query_string'].decode()
        query_params = parse_qs(query_string)
        self.user_id = query_params.get('user_id', [None])[0]

        if not self.user_id:
            await self.close()  # Close the connection if no user_id is found
            return

        self.user_id = int(self.user_id)  # Ensure user_id is an integer

        # Check if it's a group chat or direct message
        self.is_group_chat = 'group_id' in self.scope['url_route']['kwargs']
        if self.is_group_chat:
            self.group_id = self.scope['url_route']['kwargs']['group_id']
            self.room_name = f"group_{self.tenant_id}_{self.group_id}"
        else:
            self.recipient_id = self.scope['url_route']['kwargs']['recipient_id']
            if not self.recipient_id:
                await self.close()  # Close the connection if no recipient_id is found
                return
            self.recipient_id = int(self.recipient_id)  # Ensure recipient_id is an integer
            self.room_name = f"dm_{min(self.user_id, self.recipient_id)}_{max(self.user_id, self.recipient_id)}"

        # Join the appropriate room (group or DM)
        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the room when disconnecting
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')

        if self.is_group_chat:
            # Handle group chat messages
            await self.send_group_message(message)
        else:
            # Handle direct messages
            await self.send_direct_message(message)

    async def send_group_message(self, message):
        # Save the group message to the database
        await self.save_group_message_to_db(message)

        # Broadcast message to the group room
        await self.channel_layer.group_send(
            self.room_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender': self.user_id
            }
        )

    async def send_direct_message(self, message):
        # Save the direct message to the database
        await self.save_message_to_db(message)

        # Send the message to the recipient
        recipient_channel = f"dm_{min(self.user_id, self.recipient_id)}_{max(self.user_id, self.recipient_id)}"
        await self.channel_layer.group_send(
            recipient_channel,
            {
                'type': 'chat_message',
                'message': message,
                'sender': self.user_id
            }
        )

    @database_sync_to_async
    def save_group_message_to_db(self, message):
        try:
            # Get the sender, group, and tenant
            sender = User.objects.get(id=self.user_id)
            group = Group.objects.get(id=self.group_id)
            tenant = Tenant.objects.get(id=self.tenant_id)

            # Create and save the group message
            Message.objects.create(
                tenant=tenant,
                sender=sender,
                group=group,
                content=message,
                created_at=timezone.now(),
                is_read=False  # Set default to False when the message is sent
            )
        except (User.DoesNotExist, Tenant.DoesNotExist, Group.DoesNotExist) as e:
            print(f"Error saving group message: {e}")
            pass

    @database_sync_to_async
    def save_message_to_db(self, message):
        try:
            # Get the sender, recipient, and tenant
            sender = User.objects.get(id=self.user_id)
            recipient = User.objects.get(id=self.recipient_id)
            tenant = Tenant.objects.get(id=self.tenant_id)

            # Create and save the message
            Message.objects.create(
                tenant=tenant,
                sender=sender,
                recipient=recipient,
                content=message,
                created_at=timezone.now(),
                is_read=False  # Set default to False when the message is sent
            )
        except (User.DoesNotExist, Tenant.DoesNotExist) as e:
            print(f"Error saving message: {e}")
            pass

    async def chat_message(self, event):
        # Send the message to the WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender']
        }))
