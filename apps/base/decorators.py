from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect

def unauthenticated_user(view_func):
    @wraps(view_func)
    def wrapper_func(request,*args,**kwargs):
        if request.user.is_authenticated:
            return redirect("student_dashboard_root")
        else:
            return view_func(request,*args,**kwargs)
    return wrapper_func

def allowed_users(allowed=()):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper_func(request,*args,**kwargs):
            # V73: superusers pass; everyone else gets a real 403 (it used to be a 200 text page).
            if request.user.is_authenticated and (
                request.user.is_superuser or request.user.groups.filter(name__in=list(allowed)).exists()
            ):
                return view_func(request,*args,**kwargs)
            return HttpResponseForbidden("You don't have permission to view this page.")
        return wrapper_func
    return decorator