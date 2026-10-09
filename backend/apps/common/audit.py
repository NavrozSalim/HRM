SENSITIVE_PARTS = ("password", "token", "secret", "authorization", "refresh", "access")
MASK_PARTS = ("account_number", "bank_account", "routing")


def _sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_PARTS)


def _masked(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in MASK_PARTS)


def mask_account(value) -> str:
    text = "" if value is None else str(value)
    if len(text) <= 4:
        return "****"
    return f"{'*' * (len(text) - 4)}{text[-4:]}"


def sanitize(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if _sensitive(str(key)):
                cleaned[key] = "***"
            elif _masked(str(key)):
                cleaned[key] = mask_account(item)
            else:
                cleaned[key] = sanitize(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def audit(*, actor, action, summary, instance=None, model_name="", object_id="", object_repr="", changes=None, reason="", request=None):
    from apps.common.models import AuditLog

    if instance is not None:
        model_name = model_name or instance._meta.label
        object_id = object_id or str(instance.pk)
        object_repr = object_repr or str(instance)[:255]
    AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        model_name=model_name,
        object_id=str(object_id or ""),
        object_repr=(object_repr or "")[:255],
        summary=summary[:500],
        changes=sanitize(changes or {}),
        reason=reason or "",
        ip_address=client_ip(request),
    )
