import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.sessions import SessionMiddlewareStack
import chat.routing
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Whatsapp1.settings')  # Replace 'Whatsapp1' with your project name

application = ProtocolTypeRouter({
    "websocket": SessionMiddlewareStack(  # Use SessionMiddlewareStack for session handling
        URLRouter(chat.routing.websocket_urlpatterns)
    ),
})

