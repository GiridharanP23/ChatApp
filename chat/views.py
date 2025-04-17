# views.py

from django.shortcuts import render
from .models import ChatRoom

def chat_rooms(request):
    tenant = request.tenant
    if tenant:
        chat_rooms = ChatRoom.objects.filter(tenant=tenant)
    else:
        chat_rooms = ChatRoom.objects.none()  # Return no chat rooms if no tenant found
    return render(request, 'chat/chat_rooms.html', {'chat_rooms': chat_rooms})
