from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
from apps.core.utils import normalize_phone_pk

User = get_user_model()

class EmailOrPhoneModelBackend(ModelBackend):
    """
    Allows authentication using either email address or phone number or username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if not username or not password:
            return None

        # Clean input
        identifier = username.strip()
        phone_normalized = normalize_phone_pk(identifier)

        try:
            user = User.objects.get(
                Q(email__iexact=identifier) |
                Q(phone=phone_normalized) |
                Q(username__iexact=identifier)
            )
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # If multiple exist, prioritize email then phone
            user = User.objects.filter(email__iexact=identifier).first() or \
                   User.objects.filter(phone=phone_normalized).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
