from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Direct Messaging (DM) URL pattern with tenant_id
    re_path(r'ws/(?P<tenant_id>\d+)/dm/(?P<user_1_id>\d+)_(?P<user_2_id>\d+)/$', consumers.DMConsumer.as_asgi()),

    # Group chat URL pattern with tenant_id
    re_path(r'ws/(?P<tenant_id>\d+)/group/(?P<group_id>\d+)/$', consumers.GroupConsumer.as_asgi()),
]
