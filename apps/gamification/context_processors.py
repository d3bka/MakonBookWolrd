def friends_meta(request):
    """V50.7: pending friend requests for the student sidebar badge.

    Returned as a callable so the count query runs only on pages whose
    template actually renders the badge (the student shell).
    """
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return {}

    def count():
        from .friends import pending_count

        return pending_count(user)

    return {"friends_pending_count": count}
