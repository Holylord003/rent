from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import resolve


class SuspendedUserMiddleware:
    """Middleware to log out suspended users on each request."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if user is authenticated and suspended
        # Skip check for login/logout pages to avoid redirect loops
        if request.user.is_authenticated:
            try:
                # Get the current URL name
                url_name = resolve(request.path_info).url_name
                # Skip middleware for login, logout, and static files
                if url_name not in ['login', 'logout'] and not request.path_info.startswith('/static/'):
                    if hasattr(request.user, 'is_suspended') and request.user.is_suspended:
                        # Log out the suspended user
                        logout(request)
                        messages.error(request, 'Your account has been suspended. Please contact support for assistance.')
                        # Redirect to login page
                        return redirect('reviews:login')
            except Exception:
                # If URL resolution fails, continue with normal flow
                pass
        
        response = self.get_response(request)
        return response
