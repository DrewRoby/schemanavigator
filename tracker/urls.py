from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload, name='upload'),
    path('datasource/<int:pk>/', views.datasource_detail, name='datasource_detail'),
    path('schemas/', views.schema_list, name='schema_list'),
    path('compare/<int:pk1>/<int:pk2>/', views.compare_schemas, name='compare_schemas'),
]