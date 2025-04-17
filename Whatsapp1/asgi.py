import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.sessions import SessionMiddlewareStack
from django.core.asgi import get_asgi_application

import chat.routing
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Whatsapp1.settings')  # Replace 'Whatsapp1' with your project name

application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # For handling HTTP requests
    "websocket": SessionMiddlewareStack(  # Use SessionMiddlewareStack for session handling
        URLRouter(chat.routing.websocket_urlpatterns)
    ),
})

