from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tracker.urls')),
    path('api/', include('api.urls')),
    path('auth/', include('auth_detector.urls')),
    path('todo/', include('todo.urls')),
]

