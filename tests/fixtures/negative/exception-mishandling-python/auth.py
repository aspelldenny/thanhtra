import jwt
import logging

SECRET = "server-secret"
log = logging.getLogger(__name__)


def is_admin(token):
    try:
        claims = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        log.warning("token verify failed")
        return False  # fail-closed
    return claims.get("role") == "admin"
