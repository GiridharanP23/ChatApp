from django.urls import re_path
from . import consumers
from .consumers import ChatConsumer

websocket_urlpatterns = [
    # Direct Messaging (DM) URL pattern with tenant_id
    re_path(r'ws/chat/dm/(?P<recipient_id>\d+)/$', ChatConsumer.as_asgi()),
    re_path(r'ws/chat/group/(?P<group_id>\d+)/$', ChatConsumer.as_asgi()),
]
