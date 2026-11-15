from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from apps.integrations.hollihop.normalization import normalize_email, normalize_phone
from .models import UserProfile


class EmailOrPhoneModelBackend(ModelBackend):
    """Authenticate by username, exact email, or normalized phone.

    Ambiguous legacy emails intentionally fail instead of picking the first user.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        credential = (username or kwargs.get("email") or "").strip()
        if not credential or password is None:
            return None
        user = self.resolve_credential(credential)
        if user is None:
            # Same as Django's ModelBackend: hash anyway so an unknown login
            # takes as long as a wrong password (no user-enumeration by timing).
            get_user_model()().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    @staticmethod
    def resolve_credential(credential):
        """Return the single user a username / email / phone points to, active or not."""
        credential = (credential or "").strip()
        if not credential:
            return None
        User = get_user_model()
        user = None

        # Preserve normal Django username behaviour first.
        try:
            user = User._default_manager.get(username=credential)
        except User.DoesNotExist:
            pass

        if user is None and "@" in credential:
            matches = list(User._default_manager.filter(email__iexact=normalize_email(credential))[:2])
            if len(matches) == 1:
                user = matches[0]

        if user is None:
            phone = normalize_phone(credential)
            if phone:
                profiles = list(UserProfile.objects.select_related("user").filter(phone_number=phone)[:2])
                if len(profiles) == 1:
                    user = profiles[0].user
        return user
