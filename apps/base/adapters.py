from django.conf import settings
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class HollihopOnlyAccountAdapter(DefaultAccountAdapter):
    """Disable public username/email self-registration."""

    def is_open_for_signup(self, request):
        return False


class HollihopOnlySocialAccountAdapter(DefaultSocialAccountAdapter):
    """Allow social login only for already-existing accounts.

    django-allauth calls this hook when a social login would need to create a
    brand-new local user. Returning False keeps Google useful for an existing
    MakonBook account while preventing Google from becoming an alternate
    student-registration path.
    """

    def is_open_for_signup(self, request, sociallogin):
        return False
