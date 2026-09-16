from .settings_base import *  # noqa: F403
from .settings_base import INSTALLED_APPS as BASE_INSTALLED_APPS

INSTALLED_APPS = [
    *BASE_INSTALLED_APPS,
    "apps.clinical.prescription.apps.PrescriptionConfig",
    "apps.clinical.nursing.apps.NursingConfig",
    "apps.interoperability.apps.InteroperabilityConfig",
    "apps.compliance.apps.ComplianceConfig",
]

MIDDLEWARE = [
    "aegis_share.middleware.PrivateWorkflowMiddleware",
    *MIDDLEWARE,  # noqa: F405
]
