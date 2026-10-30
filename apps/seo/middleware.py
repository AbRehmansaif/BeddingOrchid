from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from .models import Redirect

class RedirectMiddleware:
    """
    Middleware that checks incoming request path against the Redirect model
    and issues an instant 301/302 response if found.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith('/static/') and not path.startswith('/media/'):
            redirect_obj = Redirect.objects.filter(old_path=path).first()
            if redirect_obj:
                if redirect_obj.is_301:
                    return HttpResponsePermanentRedirect(redirect_obj.new_path)
                return HttpResponseRedirect(redirect_obj.new_path)

        response = self.get_response(request)
        return response
