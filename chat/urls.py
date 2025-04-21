from django.urls import path
from . import views
from .views import UserRegisterView, TenantRegisterView, GroupCreateView, ChatMessageHistoryAPIView

urlpatterns = [
    path('tenant/', TenantRegisterView.as_view(), name='tenant-register'),
    path('user/', UserRegisterView.as_view(), name='user-register'),
    path('groups/', GroupCreateView.as_view(), name='group-create'),
    path('messages/<int:tenant_id>/<int:user_1_id>/<int:user_2_id>/', ChatMessageHistoryAPIView.as_view(),
         name='chat-history'),
]
