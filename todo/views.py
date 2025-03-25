from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from .models import Board, Task, Project
from .forms import BoardForm, TaskForm, ProjectForm

@login_required
def board_list(request):
    boards = Board.objects.filter(user=request.user)

    # If there are no boards, create a default one
    if not boards.exists():
        default_board = Board.objects.create(
            name="My First Board",
            user=request.user
        )
        boards = [default_board]

    context = {
        'boards': boards,
    }

    return render(request, 'todo/board_list.html', context)

@login_required
def board_detail(request, board_id):
    board = get_object_or_404(Board, id=board_id, user=request.user)
    boards = Board.objects.filter(user=request.user)
    projects = Project.objects.filter(user=request.user)

    # Get tasks for each status
    todo_tasks = Task.objects.filter(board=board, status='todo', user=request.user)
    in_progress_tasks = Task.objects.filter(board=board, status='in_progress', user=request.user)
    done_tasks = Task.objects.filter(board=board, status='done', user=request.user)

    # Forms
    task_form = TaskForm(user=request.user)

    context = {
        'board': board,
        'boards': boards,
        'projects': projects,
        'todo_tasks': todo_tasks,
        'in_progress_tasks': in_progress_tasks,
        'done_tasks': done_tasks,
        'task_form': task_form,
    }

    return render(request, 'todo/board_detail.html', context)

@login_required
def create_board(request):
    if request.method == 'POST':
        form = BoardForm(request.POST)
        if form.is_valid():
            board = form.save(commit=False)
            board.user = request.user
            board.save()
            return redirect('board_detail', board_id=board.id)
    else:
        form = BoardForm()

    return render(request, 'todo/create_board.html', {'form': form})

@login_required
def create_task(request, board_id):
    board = get_object_or_404(Board, id=board_id, user=request.user)

    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.board = board
            task.save()
            return redirect('board_detail', board_id=board.id)
    else:
        form = TaskForm(user=request.user)

    return render(request, 'todo/create_task.html', {'form': form, 'board': board})

@login_required
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    board_id = task.board.id

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('board_detail', board_id=board_id)
    else:
        form = TaskForm(instance=task, user=request.user)

    return render(request, 'todo/edit_task.html', {'form': form, 'task': task})

@login_required
@require_POST
def update_task_status(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)

    status = request.POST.get('status')
    if status in dict(Task.STATUS_CHOICES).keys():
        task.status = status
        task.save()
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid status'})

@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.user = request.user
            project.save()
            return redirect('board_list')
    else:
        form = ProjectForm()

    return render(request, 'todo/create_project.html', {'form': form})

@login_required
def project_list(request):
    projects = Project.objects.filter(user=request.user)

    context = {
        'projects': projects,
    }

    return render(request, 'todo/project_list.html', context)