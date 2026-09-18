from .settings_base import *  # noqa: F403
from .settings_base import FILE_UPLOAD_MAX_MEMORY_SIZE as BASE_UPLOAD_MEMORY_SIZE
from .settings_base import INSTALLED_APPS as BASE_INSTALLED_APPS

INSTALLED_APPS = [
    *BASE_INSTALLED_APPS,
    "apps.clinical.prescription.apps.PrescriptionConfig",
    "apps.clinical.nursing.apps.NursingConfig",
    "apps.interoperability.apps.InteroperabilityConfig",
    "apps.compliance.apps.ComplianceConfig",
    "apps.clinical.lis.apps.LisConfig",
    "apps.clinical.ris.apps.RisConfig",
    "apps.clinical.surgery.apps.SurgeryConfig",
    "apps.admin.billing.apps.BillingConfig",
    "apps.admin.inventory.apps.InventoryConfig",
]

MIDDLEWARE = [
    "aegis_share.middleware.PrivateWorkflowMiddleware",
    *MIDDLEWARE,  # noqa: F405
]

# Autenticação antes do handler de upload limitado e da verificação CSRF.
MIDDLEWARE.remove("django.contrib.auth.middleware.AuthenticationMiddleware")
_csrf_index = MIDDLEWARE.index("django.middleware.csrf.CsrfViewMiddleware")
MIDDLEWARE[_csrf_index:_csrf_index] = [
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.interoperability.upload.LaboratoryUploadMiddleware",
]

# O corpo limitado da caixa não deve ultrapassar o spool em memória do ASGI.
FILE_UPLOAD_MAX_MEMORY_SIZE = max(BASE_UPLOAD_MEMORY_SIZE, 1088 * 1024)
