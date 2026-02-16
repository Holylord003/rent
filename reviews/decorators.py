from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def staff_required(view_func):
    """Decorator to ensure user is a staff member."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to access this page.')
            return redirect('reviews:login')
        
        if not hasattr(request.user, 'user_type') or request.user.user_type != 'staffs':
            messages.error(request, 'You do not have permission to access this page. Staff access required.')
            return redirect('reviews:all_properties')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

