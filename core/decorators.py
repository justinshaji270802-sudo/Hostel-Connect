from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.contrib import messages

def admin_required(view_func):
    """
    Decorator for views that checks if the user is admin (superuser or staff)
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access this page.')
            return redirect('login')
        
        if not (request.user.is_superuser or request.user.is_staff):
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def student_required(view_func):
    """
    Decorator for views that checks if the user is a student (not admin)
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access this page.')
            return redirect('login')
        
        if request.user.is_superuser or request.user.is_staff:
            messages.error(request, 'Admin users cannot access student pages from here.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper