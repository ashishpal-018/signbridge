import re
from hashlib import pbkdf2_hmac
from hmac import compare_digest
import secrets

from .database import create_user, find_user

VALID_ROLES = {"blind", "deaf"}

def validate_password_strength(password: str):
    """
    Checks if a password meets basic security criteria:
    - At least 8 characters long
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    return True, "Password is valid."

def sanitize_username(username: str):
    """
    Cleans and validates the username input to prevent bad characters.
    Only allows letters, numbers, and underscores.
    """
    clean_username = username.strip()
    if not re.fullmatch(r"[a-zA-Z0-9_]{3,32}", clean_username):
        return False, "Username must be at least 3 alphanumeric characters."
    return True, clean_username


def _hash_password(password: str, salt: bytes) -> str:
    return pbkdf2_hmac("sha256", password.encode(), salt, 120_000).hex()


def register_user(username: str, password: str, role: str) -> tuple[bool, str]:
    valid_username, clean_username = sanitize_username(username)
    if not valid_username:
        return False, clean_username
    valid_password, message = validate_password_strength(password)
    if not valid_password:
        return False, message
    if role not in VALID_ROLES:
        return False, "Please select a valid learning mode."
    salt = secrets.token_bytes(16)
    if not create_user(clean_username, _hash_password(password, salt), salt.hex(), role):
        return False, "That username is already registered."
    return True, "Account created. You can now log in."


def authenticate_user(username: str, password: str) -> tuple[bool, str]:
    user = find_user(username.strip())
    if user is None:
        return False, "Invalid username or password."
    expected = _hash_password(password, bytes.fromhex(user["salt"]))
    if not compare_digest(expected, user["password_hash"]):
        return False, "Invalid username or password."
    return True, user["role"]