from app.models.user import User, UserRole

OWNERSHIP_PERMISSIONS = (
    "business.read",
    "business.create",
    "business.update",
    "business.delete",
)

ADMIN_PERMISSION_CATALOG: list[str] = [
    "business.read",
    "business.create",
    "business.update",
    "business.delete",
    "business.approve",
    "business.license.verify",
    "review.read",
    "review.create",
    "review.moderate",
    "review.reply",
    "category.read",
    "category.manage",
    "category.suggestion.manage",
    "quote.read",
    "quote.create",
    "quote.manage",
    "ad.manage",
    "stats.read",
    "notification.manage",
    "user.read",
    "user.manage",
    "user.role.manage",
    "admin.settings.manage",
    "admin.audit.read",
    "admin.dev",
]


def permission_catalog() -> list[dict]:
    return [
        {"code": code, "label": code, "group": code.split(".")[0]}
        for code in sorted(set(ADMIN_PERMISSION_CATALOG))
    ]


def has_permission(user: User | None, code: str) -> bool:
    if user is None:
        return False
    if user.role == UserRole.SUPERADMIN:
        return True
    # Granular permissions are only meaningful for the admin role. A demoted
    # admin must not keep endpoint access through a stale permission list.
    if user.role != UserRole.ADMIN:
        return False
    return code in (user.permissions or [])


def has_role(user: User | None, *roles: UserRole) -> bool:
    if user is None:
        return False
    return user.role in roles


def validate_permission_codes(codes: list[str]) -> list[str]:
    from app.core.errors import AppError

    cleaned = list(dict.fromkeys(codes))
    unknown = sorted(set(cleaned) - set(ADMIN_PERMISSION_CATALOG))
    if unknown:
        raise AppError(
            "validation_error",
            "unknown_permissions",
            422,
            {"permissions": unknown},
        )
    return cleaned
