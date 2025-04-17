import json
import logging
from urllib.parse import parse_qs
import redis
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
active_users = {}
logger = logging.getLogger(__name__)

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

class DMConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        self.user_1_id = self.scope['url_route']['kwargs']['user_1_id']
        self.user_2_id = self.scope['url_route']['kwargs']['user_2_id']

        self.user_id = self.scope['query_string'].decode().split('=')[-1]  # Extract user_id from query param
        self.room_name = f'dm_{self.tenant_id}_{self.user_1_id}_{self.user_2_id}'

        await self.channel_layer.group_add(self.room_name, self.channel_name)
        active_users[self.user_id] = self.channel_name
        await self.accept()

        await self.deliver_undelivered_messages(self.user_id)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_name, self.channel_name)
        if self.user_id in active_users:
            del active_users[self.user_id]

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        sender = text_data_json.get('user', 'Anonymous')
        recipient = self.user_2_id if self.user_id == self.user_1_id else self.user_1_id

        if recipient in active_users:
            await self.channel_layer.send(
                active_users[recipient],
                {
                    'type': 'chat_message',
                    'message': message,
                    'user': sender
                }
            )
        else:
            self.store_message_in_queue(recipient, message, sender)

    def store_message_in_queue(self, user_id, message, sender):
        redis_client.lpush(f"user:{user_id}:messages", json.dumps({
            'message': message,
            'sender': sender,
            'status': 'pending'
        }))

    async def deliver_undelivered_messages(self, user_id):
        while True:
            message_data = redis_client.rpop(f"user:{user_id}:messages")
            if message_data:
                message_data = json.loads(message_data)
                await self.send(text_data=json.dumps({
                    'message': message_data['message'],
                    'user': message_data['sender']
                }))
            else:
                break

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'user': event.get('user', 'Unknown')
        }))


class GroupConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get group_id from the URL
        self.group_id = self.scope['url_route']['kwargs']['group_id']

        # Create a unique group name based on the group_id
        self.room_name = f'group_{self.group_id}'

        # Add the user to the group room
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        # Remove the user from the group room
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Receive the message sent by the user
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        user = text_data_json.get('user', 'Anonymous')

        # Broadcast the message to all group members
        await self.channel_layer.group_send(
            self.room_name,
            {
                'type': 'chat_message',
                'message': message,
                'user': user
            }
        )

    async def chat_message(self, event):
        # Send the message to the WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'user': event['user']
        }))
