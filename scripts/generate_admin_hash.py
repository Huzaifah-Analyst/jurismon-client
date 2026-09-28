"""Generates a bcrypt hash for the JurisMon admin password.

Usage:
    python scripts/generate_admin_hash.py                 # generate a strong password
    python scripts/generate_admin_hash.py "my-password"   # hash a chosen password

Copy the resulting ADMIN_PASSWORD_HASH line into your .env file.
"""

import sys
import os
import secrets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.auth import get_password_hash


def main() -> None:
    if len(sys.argv) > 1:
        password = sys.argv[1]
        generated = False
    else:
        password = secrets.token_urlsafe(18)
        generated = True

    password_hash = get_password_hash(password)

    print()
    if generated:
        print("Generated password (store this in your password manager now):")
        print(f"    {password}")
        print()
    print("Add this line to your .env file:")
    print(f"    ADMIN_PASSWORD_HASH={password_hash}")
    print()
    print("The plaintext password is never stored on the server.")
    print()


if __name__ == "__main__":
    main()
