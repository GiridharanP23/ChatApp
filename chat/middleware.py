# chat/middleware.py

from django.utils.deprecation import MiddlewareMixin
from .models import Tenant

class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        tenant_name = request.META.get('HTTP_X_TENANT', None)  # Get tenant from headers (or URL)

        if tenant_name:
            try:
                tenant = Tenant.objects.get(name=tenant_name)
                request.tenant = tenant  # Attach tenant to request
            except Tenant.DoesNotExist:
                request.tenant = None  # No tenant found
        else:
            request.tenant = None  # No tenant provided
