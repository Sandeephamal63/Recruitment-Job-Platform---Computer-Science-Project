from functools import wraps

from flask_jwt_extended import get_jwt

from .errors import ForbiddenError


def role_required(*roles: str):
    """Guard a route to one of the given JWT ``role`` claims.

    Stack this *beneath* ``@jwt_required()`` so the token (and its claims) is
    verified before this decorator reads the role.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            role = get_jwt().get("role")
            if role not in roles:
                raise ForbiddenError("You do not have permission to perform this action")
            return fn(*args, **kwargs)

        return wrapper

    return decorator