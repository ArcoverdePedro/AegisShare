from django.contrib.auth.models import Group, Permission
from django.core.management import BaseCommand, CommandError
from django.db import transaction

# Proposta (G01/G02 pendentes): grupos nao concedem acesso a pacientes (vinculo PEP/unidade ADT
# continua obrigatorio) e nenhum usuario e associado por este comando.
ROLE_MATRIX = {
    "Recepção": [
        "scheduling.view_agenda",
        "scheduling.book_appointment",
        "scheduling.checkin_appointment",
        "adt.view_bed_map",
        "billing.view_accounts",
        "billing.open_account",
    ],
    "Médico": [
        "prescription.view_medication_request",
        "prescription.prescribe_medication",
        "prescription.cancel_medication_request",
        "lis.view_orders",
        "lis.order_test",
        "ris.view_orders",
        "ris.order_exam",
        "surgery.view_cases",
        "surgery.request_procedure",
        "adt.view_bed_map",
        "adt.view_movement_history",
        "adt.admit_patient",
        "adt.transfer_patient",
        "adt.discharge_patient",
        "nursing.view_nursing",
        "scheduling.view_agenda",
    ],
    "Enfermagem": [
        "nursing.view_nursing",
        "nursing.record_vitals",
        "nursing.administer_medication",
        "prescription.view_medication_request",
        "adt.view_bed_map",
        "adt.view_movement_history",
        "adt.manage_bed_status",
        "lis.view_orders",
        "lis.collect_specimen",
        "inventory.view_requisitions",
        "inventory.request_material",
        "inventory.move_stock",
        "scheduling.view_agenda",
        "scheduling.checkin_appointment",
    ],
    "Farmácia": [
        "prescription.view_medication_request",
        "prescription.validate_medication_request",
        "prescription.view_pharmacy_stock",
        "prescription.manage_pharmacy_stock",
        "prescription.view_medication_dispense",
        "prescription.dispense_medication",
        "prescription.manage_drug_catalog",
    ],
    "Laboratório": [
        "lis.view_orders",
        "lis.collect_specimen",
        "lis.receive_specimen",
        "lis.cancel_order",
        "interoperability.view_lab_inbox",
        "interoperability.receive_lab_file",
    ],
    "Imagem": ["ris.view_orders"],
    "Centro cirúrgico": ["surgery.view_cases", "surgery.schedule_case", "scheduling.view_agenda"],
    "Faturamento": [
        "billing.view_accounts",
        "billing.open_account",
        "billing.add_item",
        "billing.reverse_item",
        "billing.close_account",
    ],
    "Suprimentos": [
        "inventory.view_requisitions",
        "inventory.move_stock",
        "inventory.adjust_stock",
        "inventory.view_purchases",
        "inventory.request_purchase",
        "inventory.receive_purchase",
    ],
    "Suprimentos · aprovação": ["inventory.view_purchases", "inventory.approve_purchase"],
    "RH": [
        "hr.view_employee",
        "hr.add_employee",
        "hr.change_employee",
        "hr.view_employeeabsence",
        "hr.add_employeeabsence",
        "hr.change_employeeabsence",
    ],
    "Privacidade": [
        "compliance.view_requests",
        "compliance.register_request",
        "compliance.process_request",
    ],
}
PREFIX = "HIS · "


def _permissions(names):
    found = {}
    for name in names:
        app, codename = name.split(".")
        found[name] = Permission.objects.filter(
            content_type__app_label=app, codename=codename
        ).first()
    missing = [name for name, perm in found.items() if perm is None]
    if missing:
        raise CommandError(f"Permissões inexistentes: {', '.join(missing)}")
    return list(found.values())


class Command(BaseCommand):
    help = "Mostra (ou, com --apply, cria) grupos de papel propostos. Não associa usuários."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        with transaction.atomic():
            for role, names in ROLE_MATRIX.items():
                permissions = _permissions(names)
                self.stdout.write(f"{PREFIX}{role}: {', '.join(names)}")
                if options["apply"]:
                    group, _ = Group.objects.get_or_create(name=f"{PREFIX}{role}")
                    group.permissions.set(permissions)
        if not options["apply"]:
            self.stdout.write("Simulação: use --apply para gravar os grupos.")
