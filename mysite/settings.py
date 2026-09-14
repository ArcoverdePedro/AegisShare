from .settings_base import *  # noqa: F401,F403

INSTALLED_APPS = [  # noqa: F405
    *INSTALLED_APPS,
    "apps.clinical.prescription.apps.PrescriptionConfig",
]
