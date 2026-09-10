from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="OMA Flowers API",
        default_version='v1',
        description="API documentation for OMA Flowers platform",
        terms_of_service="https://www.omaflowers.com/terms/",
        contact=openapi.Contact(email="support@omaflowers.com"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API URLs
    path('api/v1/auth/', include('users.urls')),
    path('api/v1/distributors/', include('distributors.urls')),
    path('api/v1/shops/', include('shops.urls')),
    path('api/v1/', include('products.urls')),
    path('api/v1/orders/', include('orders.urls')),
    path('api/v1/commissions/', include('commissions.urls')),
    path('api/v1/bonuses/', include('bonuses.urls')),
    path('api/v1/awards/', include('awards.urls')),
    path('api/v1/blog/', include('blog.urls')),
    path('api/v1/carts/', include('cart.urls')),
    
    
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)