from django.contrib import admin
from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'date', 'is_completed', 'created_at')
    list_filter = ('is_completed', 'date')
    search_fields = ('title', 'description')
