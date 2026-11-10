from app.core.permissions import has_permission
from app.models.user import User, UserRole


def _user(role: UserRole, permissions: list[str]) -> User:
    return User(phone="9123456789", role=role, permissions=permissions)


def test_customer_keeps_no_access_through_stale_permissions():
    user = _user(UserRole.CUSTOMER, ["business.approve", "user.manage"])
    assert has_permission(user, "business.approve") is False
    assert has_permission(user, "user.manage") is False


def test_owner_keeps_no_admin_access():
    user = _user(UserRole.OWNER, ["business.approve"])
    assert has_permission(user, "business.approve") is False


def test_admin_access_is_limited_to_granted_permissions():
    user = _user(UserRole.ADMIN, ["business.approve"])
    assert has_permission(user, "business.approve") is True
    assert has_permission(user, "user.manage") is False


def test_superadmin_has_every_permission():
    user = _user(UserRole.SUPERADMIN, [])
    assert has_permission(user, "anything.at.all") is True
