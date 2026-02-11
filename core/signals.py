from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def google_login_success(sender, request, user, **kwargs):
    if not request:
        return
    path = request.path or ""
    if "accounts/google" in path:
        messages.success(request, "Signed in with Google.")
