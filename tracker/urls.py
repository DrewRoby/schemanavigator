from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload, name='upload'),
    path('datasource/<int:pk>/', views.datasource_detail, name='datasource_detail'),
    path('schemas/', views.schema_list, name='schema_list'),
    path('compare/<int:pk1>/<int:pk2>/', views.compare_schemas, name='compare_schemas'),
    path('datasource/<int:pk>/retry/', views.retry_detection, name='retry_detection'),
    path('datasource/<int:pk>/reprocess/', views.reprocess_file, name='reprocess_file'),
    path('datasource/<int:pk>/delete/', views.delete_datasource, name='delete_datasource'),
]