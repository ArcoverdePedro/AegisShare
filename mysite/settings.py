from .settings_base import *  # noqa: F401,F403
from .settings_base import INSTALLED_APPS as BASE_INSTALLED_APPS

INSTALLED_APPS = [
    *BASE_INSTALLED_APPS,
    "apps.clinical.prescription.apps.PrescriptionConfig",
]
