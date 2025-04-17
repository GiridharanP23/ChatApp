from django.contrib import admin

from chat.models import Message, Group, Tenant

admin.site.register(Tenant)
admin.site.register(Group)
admin.site.register(Message)