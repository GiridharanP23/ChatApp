# consumers.py

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Retrieve room_name and tenant_name from the URL parameters
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.tenant_name = self.scope['url_route']['kwargs']['tenant_name']

        # Create a unique group name based on both room_name and tenant_name
        self.room_group_name = f'chat_{self.tenant_name}_{self.room_name}'

        # Add the user to the group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        # Remove the user from the group when disconnected
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            # Parse the incoming message
            text_data_json = json.loads(text_data)
            message = text_data_json['message']

            # Send the message to the group for the current room and tenant
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'user': text_data_json.get('user', 'Anonymous')  # Use the 'user' sent by the client
                }
            )

        except KeyError:
            logger.error("Received message is missing the 'message' field")
        except json.JSONDecodeError:
            logger.error("Error decoding JSON in the received message")
        except Exception as e:
            logger.error(f"An error occurred: {e}")

    async def chat_message(self, event):
        message = event['message']
        user = event.get('user', 'Unknown')

        # Send the message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'user': user
        }))
