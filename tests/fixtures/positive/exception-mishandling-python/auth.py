import jwt

SECRET = "server-secret"


def is_admin(token):
    try:
        claims = jwt.decode(token, SECRET, algorithms=["HS256"])
        return claims.get("role") == "admin"
    except Exception:
        pass
    # FAIL-OPEN: token verify failed but we still grant admin
    return True
