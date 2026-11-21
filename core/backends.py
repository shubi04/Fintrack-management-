from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """Log in with email OR the old username, so existing users keep working."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        User = get_user_model()
        user = User.objects.filter(Q(email__iexact=username) | Q(username__iexact=username)).first()
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
