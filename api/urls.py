# urls.py
from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('images/', views.get_images, name='get_images'),
    path('images/random/', views.get_random_image, name='get_random_image'),
]

