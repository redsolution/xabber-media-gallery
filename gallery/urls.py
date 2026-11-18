from django.contrib import admin
from django.urls import path, include
from django.conf.urls import url
from django.views.static import serve
from django.conf import settings

urlpatterns = [
    # url(r'^gallery/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}), # Only for dev
    path('api/v1/', include('gallery.api.urls')),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('admin/', admin.site.urls),
]
