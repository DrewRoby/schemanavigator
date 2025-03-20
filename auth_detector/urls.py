from django.urls import path
from . import views

urlpatterns = [
    path('auth-check.png', views.auth_check_image, name='auth_check_image'),
]