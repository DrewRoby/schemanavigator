from django.urls import path
from . import views

urlpatterns = [
    path('', views.board_list, name='board_list'),
    path('board/<int:board_id>/', views.board_detail, name='board_detail'),
    path('board/create/', views.create_board, name='create_board'),
    path('board/<int:board_id>/task/create/', views.create_task, name='create_task'),
    path('task/<int:task_id>/edit/', views.edit_task, name='edit_task'),
    path('task/<int:task_id>/status/', views.update_task_status, name='update_task_status'),
    path('projects/', views.project_list, name='project_list'),
    path('project/create/', views.create_project, name='create_project'),
]