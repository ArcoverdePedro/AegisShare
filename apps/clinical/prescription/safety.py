from hashlib import sha256

from auditlog.context import set_actor
from django.db import transaction
from django.utils import timezone

from .models import (
    DoseRule,
    Interaction,
    MedicationRequest,
    MedicationSafetyFinding,
    MedicationSafetyReview,
)


class SafetyStateError(RuntimeError):
    """Falha segura de revisão farmacêutica sem expor PHI."""


def _approved_interactions(drug_ids):
    return Interaction.objects.filter(
        active=True,
        approved_by__isnull=False,
        approved_at__isnull=False,
        reference_source__gt="",
        reference_version__gt="",
        drug_a_id__in=drug_ids,
        drug_b_id__in=drug_ids,
    ).select_related("drug_a", "drug_b")


def _approved_dose_rules(drug_ids):
    return DoseRule.objects.filter(
        active=True,
        approved_by__isnull=False,
        approved_at__isnull=False,
        reference_source__gt="",
        reference_version__gt="",
        drug_id__in=drug_ids,
    ).select_related("drug")


def _reference_fingerprint(interactions, dose_rules):
    tokens = {
        *(
            f"interaction:{item.pk}:{item.reference_source}:{item.reference_version}"
            for item in interactions
        ),
        *(
            f"dose:{item.pk}:{item.reference_source}:{item.reference_version}"
            for item in dose_rules
        ),
    }
    payload = "|".join(sorted(tokens)) or "no-approved-reference"
    return f"sha256:{sha256(payload.encode()).hexdigest()}"


def _age_days(patient):
    return (timezone.localdate() - patient.birth_date).days


def _rule_applies_to_age(rule, age_days):
    if rule.min_age_days is not None and age_days < rule.min_age_days:
        return False
    if rule.max_age_days is not None and age_days > rule.max_age_days:
        return False
    return True


def evaluate_medication_safety(medication_request):
    """Avalia somente referências estruturadas, ativas e aprovadas.

    Peso e alergia estruturada não possuem fonte aprovada nesta versão. Portanto,
    regras que dependem de peso ficam explicitamente NOT_EVALUABLE e alergia nunca
    recebe um falso resultado negativo.
    """
    if medication_request.status != MedicationRequest.Status.SUBMITTED:
        raise SafetyStateError("A revisão farmacêutica exige prescrição submetida.")

    items = list(
        medication_request.items.select_related("drug").order_by("sequence", "created_at")
    )
    if not items:
        raise SafetyStateError("A prescrição não possui itens para revisão.")

    item_by_drug = {item.drug_id: item for item in items}
    drug_ids = set(item_by_drug)
    interactions = list(_approved_interactions(drug_ids))
    dose_rules = list(_approved_dose_rules(drug_ids))
    rules_by_drug = {}
    for rule in dose_rules:
        rules_by_drug.setdefault(rule.drug_id, []).append(rule)

    findings = []
    blocking_findings = 0
    warning_findings = 0

    for interaction in interactions:
        if interaction.drug_a_id == interaction.drug_b_id:
            continue
        finding = {
            "kind": MedicationSafetyFinding.Kind.INTERACTION,
            "request_item": item_by_drug.get(interaction.drug_a_id),
            "interaction": interaction,
            "dose_rule": None,
            "severity": interaction.severity,
            "blocking": interaction.blocking,
        }
        findings.append(finding)
        if interaction.blocking:
            blocking_findings += 1
        else:
            warning_findings += 1

    age_days = _age_days(medication_request.encounter.patient)
    dose_status = MedicationSafetyReview.DoseStatus.PASS
    any_dose_evaluable = False
    any_dose_not_evaluable = False

    for item in items:
        rules = rules_by_drug.get(item.drug_id, [])
        if not rules:
            any_dose_not_evaluable = True
            findings.append(
                {
                    "kind": MedicationSafetyFinding.Kind.DOSE,
                    "request_item": item,
                    "interaction": None,
                    "dose_rule": None,
                    "severity": MedicationSafetyReview.DoseStatus.NOT_EVALUABLE,
                    "blocking": False,
                }
            )
            continue

        item_had_evaluable_rule = False
        item_had_not_evaluable_rule = False
        for rule in rules:
            depends_on_weight = rule.basis in {
                DoseRule.Basis.WEIGHT,
                DoseRule.Basis.AGE_AND_WEIGHT,
            } or rule.per_kg
            if depends_on_weight:
                item_had_not_evaluable_rule = True
                findings.append(
                    {
                        "kind": MedicationSafetyFinding.Kind.DOSE,
                        "request_item": item,
                        "interaction": None,
                        "dose_rule": rule,
                        "severity": MedicationSafetyReview.DoseStatus.NOT_EVALUABLE,
                        "blocking": False,
                    }
                )
                continue

            if rule.basis != DoseRule.Basis.AGE or not _rule_applies_to_age(rule, age_days):
                continue
            if item.dose_unit.strip().casefold() != rule.dose_unit.strip().casefold():
                item_had_not_evaluable_rule = True
                findings.append(
                    {
                        "kind": MedicationSafetyFinding.Kind.DOSE,
                        "request_item": item,
                        "interaction": None,
                        "dose_rule": rule,
                        "severity": MedicationSafetyReview.DoseStatus.NOT_EVALUABLE,
                        "blocking": False,
                    }
                )
                continue

            item_had_evaluable_rule = True
            any_dose_evaluable = True
            outside_reference = (
                rule.min_dose is not None and item.dose < rule.min_dose
            ) or (rule.max_dose is not None and item.dose > rule.max_dose)
            if outside_reference:
                blocking_findings += 1
                dose_status = MedicationSafetyReview.DoseStatus.BLOCKED
                findings.append(
                    {
                        "kind": MedicationSafetyFinding.Kind.DOSE,
                        "request_item": item,
                        "interaction": None,
                        "dose_rule": rule,
                        "severity": MedicationSafetyReview.DoseStatus.BLOCKED,
                        "blocking": True,
                    }
                )

        if item_had_not_evaluable_rule or not item_had_evaluable_rule:
            any_dose_not_evaluable = True

    if dose_status != MedicationSafetyReview.DoseStatus.BLOCKED:
        if any_dose_not_evaluable or not any_dose_evaluable:
            dose_status = MedicationSafetyReview.DoseStatus.NOT_EVALUABLE
        else:
            dose_status = MedicationSafetyReview.DoseStatus.PASS

    return {
        "findings": findings,
        "blocking_findings": blocking_findings,
        "warning_findings": warning_findings,
        "dose_status": dose_status,
        "reference_version": _reference_fingerprint(interactions, dose_rules),
        "allergy_source_available": False,
    }


@transaction.atomic
def record_medication_safety_review(
    *,
    medication_request,
    actor,
    manual_allergy_review_confirmed,
):
    snapshot = evaluate_medication_safety(medication_request)
    allergy_status = (
        MedicationSafetyReview.AllergyStatus.REVIEW_CONFIRMED
        if manual_allergy_review_confirmed
        else MedicationSafetyReview.AllergyStatus.UNAVAILABLE
    )
    with set_actor(actor):
        review = MedicationSafetyReview.objects.create(
            medication_request=medication_request,
            reviewed_by=actor,
            allergy_status=allergy_status,
            dose_status=snapshot["dose_status"],
            blocking_findings=snapshot["blocking_findings"],
            warning_findings=snapshot["warning_findings"],
            reference_version=snapshot["reference_version"],
        )
        for finding in snapshot["findings"]:
            MedicationSafetyFinding.objects.create(
                review=review,
                kind=finding["kind"],
                request_item=finding["request_item"],
                interaction=finding["interaction"],
                dose_rule=finding["dose_rule"],
                severity=finding["severity"],
                blocking=finding["blocking"],
            )
    return review
