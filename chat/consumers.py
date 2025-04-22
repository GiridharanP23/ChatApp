import json
import logging
from urllib.parse import parse_qs
import os
import django
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Whatsapp1.settings')
django.setup()
import redis
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

from chat.models import Tenant, Message, Group, Room

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
active_users = {}
logger = logging.getLogger(__name__)

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)
MESSAGES_PER_PAGE = 20
User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']

        query_string = self.scope['query_string'].decode()
        query_params = parse_qs(query_string)
        self.user_id = query_params.get('user_id', [None])[0]

        if not self.user_id:
            await self.close()
            return

        self.user_id = int(self.user_id)
        self.user = await self.get_user(self.user_id)

        self.is_group_chat = 'group_id' in self.scope['url_route']['kwargs']
        if self.is_group_chat:
            self.group_id = int(self.scope['url_route']['kwargs']['group_id'])
            self.room_name = f"group_{self.tenant_id}_{self.group_id}"
        else:
            self.recipient_id = self.scope['url_route']['kwargs'].get('recipient_id')
            if not self.recipient_id:
                await self.close()
                return
            self.recipient_id = int(self.recipient_id)
            self.room_name = f"dm_{self.tenant_id}_{min(self.user_id, self.recipient_id)}_{max(self.user_id, self.recipient_id)}"

        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

        # 🔹 Mark all messages as read in direct message room after connecting
        if not self.is_group_chat:
            await self.mark_all_dm_messages_as_read()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    @database_sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')

        if not message:
            return

        if self.is_group_chat:
            message_obj = await self.save_group_message(message)
        else:
            message_obj = await self.save_direct_message(message)

        if not message_obj:
            await self.send(text_data=json.dumps({
                'error': 'Failed to save message'
            }))
            return

        await self.channel_layer.group_send(
            self.room_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender_id': self.user_id,
                'message_id': message_obj.id,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'message_id': event['message_id']
        }))
        if self.user.id != event['sender_id']:
            await self.mark_message_as_read(event['message_id'])

    @database_sync_to_async
    def save_group_message(self, content):
        try:
            sender = User.objects.get(id=self.user_id)
            tenant = Tenant.objects.get(id=self.tenant_id)
            group = Group.objects.get(id=self.group_id, tenant=tenant)
            room = Room.objects.get(tenant=tenant, group=group, room_type='group')

            return Message.objects.create(
                tenant=tenant,
                sender=sender,
                room=room,
                content=content,
                is_read=False,
                created_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Error saving group message: {e}")
            return None

    @database_sync_to_async
    def save_direct_message(self, content):
        try:
            sender = User.objects.get(id=self.user_id)
            recipient = User.objects.get(id=self.recipient_id)
            tenant = Tenant.objects.get(id=self.tenant_id)

            room_name = f"dm_{self.tenant_id}_{min(sender.id, recipient.id)}_{max(sender.id, recipient.id)}"
            room, created = Room.objects.get_or_create(
                tenant=tenant,
                room_type='dm',
                name=room_name
            )
            room.participants.set([sender, recipient])

            return Message.objects.create(
                tenant=tenant,
                sender=sender,
                room=room,
                content=content,
                is_read=False,
                created_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Error saving direct message: {e}")
            return None

    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        Message.objects.filter(id=message_id).update(is_read=True)

    @database_sync_to_async
    def mark_all_dm_messages_as_read(self):
        try:
            tenant = Tenant.objects.get(id=self.tenant_id)
            room_name = f"dm_{self.tenant_id}_{min(self.user_id, self.recipient_id)}_{max(self.user_id, self.recipient_id)}"
            room = Room.objects.get(name=room_name, tenant=tenant, room_type='dm')

            Message.objects.filter(
                room=room,
                is_read=False,
                sender_id=self.recipient_id  # Only mark messages *from* the recipient as read
            ).update(is_read=True)
        except Exception as e:
            logger.error(f"Error marking messages as read on connect: {e}")
