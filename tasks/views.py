from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import RegisterForm, TaskForm
from .models import Task


# Authentication Views
def register_view(request):
    if request.user.is_authenticated:
        return redirect('tasks:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful. You can now log in.')
            return redirect('tasks:login')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('tasks:dashboard')

    next_url = request.POST.get('next') or request.GET.get('next') or ''

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('tasks:dashboard')
    else:
        form = AuthenticationForm(request)

    for field in form.fields.values():
        field.widget.attrs.update({'class': 'form-input'})

    return render(request, 'registration/login.html', {'form': form, 'next': next_url})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('tasks:login')


# Dashboard & Task Views
@login_required
def dashboard_view(request):
    user_tasks = Task.objects.filter(user=request.user)
    today = timezone.localdate()

    # Aggregate counts via ORM
    stats = user_tasks.aggregate(
        total_count=Count('id'),
        completed_count=Count('id', filter=Q(is_completed=True)),
        pending_count=Count('id', filter=Q(is_completed=False)),
    )
    total_count = stats['total_count'] or 0
    completed_count = stats['completed_count'] or 0
    pending_count = stats['pending_count'] or 0
    completion_rate = round((completed_count / total_count * 100), 1) if total_count > 0 else 0

    # Filter tasks by schedule
    today_tasks = user_tasks.filter(date=today).order_by('-created_at')
    history_tasks = user_tasks.filter(date__lt=today).order_by('-date', '-created_at')
    upcoming_tasks = user_tasks.filter(date__gt=today).order_by('date', '-created_at')

    context = {
        'tasks': user_tasks.order_by('-date', '-created_at'),
        'total_count': total_count,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'completion_rate': completion_rate,
        'today': today,
        'today_tasks': today_tasks,
        'history_tasks': history_tasks,
        'upcoming_tasks': upcoming_tasks,
    }
    return render(request, 'tasks/dashboard.html', context)


@login_required
def task_history_view(request):
    today = timezone.localdate()
    history_tasks = Task.objects.filter(user=request.user, date__lt=today).order_by('-date', '-created_at')
    context = {
        'history_tasks': history_tasks,
        'today': today,
    }
    return render(request, 'tasks/task_history.html', context)


@login_required
def task_list_view(request):
    tasks = Task.objects.filter(user=request.user).order_by('-date', '-created_at')
    return render(request, 'tasks/task_list.html', {'tasks': tasks})


@login_required
def task_create_view(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, 'Task created successfully.')
            return redirect('tasks:task_list')
    else:
        form = TaskForm()

    return render(request, 'tasks/task_form.html', {
        'form': form,
        'action': 'Create',
    })


@login_required
def task_detail_view(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    return render(request, 'tasks/task_detail.html', {'task': task})


@login_required
def task_update_view(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Task updated successfully.')
            return redirect('tasks:task_list')
    else:
        form = TaskForm(instance=task)

    return render(request, 'tasks/task_form.html', {
        'form': form,
        'task': task,
        'action': 'Edit',
    })


@login_required
def task_delete_view(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        task_title = task.title
        task.delete()
        messages.success(request, f'Task "{task_title}" was deleted successfully.')
        return redirect('tasks:task_list')
    return render(request, 'tasks/task_confirm_delete.html', {'task': task})


@login_required
@require_POST
def task_toggle_complete_view(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    task.is_completed = not task.is_completed
    task.save(update_fields=['is_completed'])
    status_text = 'completed' if task.is_completed else 'pending'
    messages.success(request, f'Task "{task.title}" marked as {status_text}.')
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('tasks:task_list')
