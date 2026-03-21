import bcrypt

_ROUNDS = 12


def _secret_bytes(plain: str) -> bytes:
    # Bcrypt uses at most the first 72 bytes of the password.
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=_ROUNDS)
    return bcrypt.hashpw(_secret_bytes(plain), salt).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_secret_bytes(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False
