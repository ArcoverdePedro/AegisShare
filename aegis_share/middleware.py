from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import get_user_model


class FirstAccessRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.User = get_user_model()
        self.SETUP_URL = reverse("primeiro_cadastro")

    def __call__(self, request):
        superuser_exists = self.User.objects.filter(is_superuser=True).exists()

        current_path = request.path

        if (
            not superuser_exists
            and not current_path.startswith(self.SETUP_URL)
            and not current_path.startswith("/static/")
            and not current_path.startswith("/media/")
        ):
            return redirect(self.SETUP_URL)

        response = self.get_response(request)
        return response
