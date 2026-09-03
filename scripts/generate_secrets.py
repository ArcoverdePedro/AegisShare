#!/usr/bin/env python3
import base64
import secrets


def main():
    secret_key = secrets.token_urlsafe(64)
    file_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")

    print("SECRET_KEY=" + secret_key)
    print("FILE_ENCRYPTION_KEY=" + file_key)


if __name__ == "__main__":
    main()
