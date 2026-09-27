from .base import *  # noqa

DEBUG = True

SECRET_KEY = "dev-insecure-secret-key-changez-moi"

ALLOWED_HOSTS = ["*"]

try:
    from .local import *  # noqa
except ImportError:
    pass
