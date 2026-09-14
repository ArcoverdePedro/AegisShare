import hashlib
from dataclasses import dataclass
from uuid import UUID

from django.utils import timezone

from .models import (
    DoseRule,
    Interaction,
    MedicationRequest,
    MedicationSafetyFinding,
    MedicationSafetyReview,
)


class SafetyEvaluationError(RuntimeError):
    """Erro seguro de avaliação, sem PHI ou conteúdo clínico livre."""


class SafetyStateError(SafetyEvaluationError):
    pass


class SafetyReferenceError(SafetyEvaluationError):
    pass


@dataclass(frozen=True, slots=True)
class SafetyFindingResult:
    kind: str
    severity: str
    blocking: bool
    reason_code: str
    request_item_id: UUID | None = None
    interaction_id: UUID | None = None
    dose_rule_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class SafetyEvaluation:
    allergy_status: str
    dose_status: str
    blocking_findings: int
    warning_findings: int
    reference_version: str
    findings: tuple[SafetyFindingResult, ...]


_REASON_INTERACTION = "INTERACTION_CONFIGURED"
_REASON_WEIGHT_UNAVAILABLE = "DOSE_WEIGHT_UNAVAILABLE"
_REASON_AGE_UNAVAILABLE = "DOSE_AGE_UNAVAILABLE"
_REASON_UNIT_MISMATCH = "DOSE_UNIT_MISMATCH"
_REASON_NO_LIMIT = "DOSE_RULE_WITHOUT_LIMIT"
_REASON_OUTSIDE_RULE = "DOSE_OUTSIDE_RULE"
_REASON_NO_APPLICABLE_RULE = "DOSE_NO_APPLICABLE_RULE"


def _is_governed_reference(reference):
    return bool(
        reference.reference_source
        and reference.reference_version
        and reference.approved_by_id
        and reference.approved_at
    )


def _encounter_age_days(medication_request):
    birth_date = medication_request.encounter.patient.birth_date
    started_at = medication_request.encounter.started_at
    if timezone.is_aware(started_at):
        encounter_date = timezone.localtime(started_at).date()
    else:
        encounter_date = started_at.date()
    age_days = (encounter_date - birth_date).days
    return age_days if age_days >= 0 else None


def _reference_set_version(interactions, dose_rules):
    tokens = [
        f"I:{interaction.pk}:{interaction.reference_version}"
        for interaction in interactions
    ]
    tokens.extend(f"D:{rule.pk}:{rule.reference_version}" for rule in dose_rules)
    payload = "\n".join(sorted(tokens)).encode()
    digest = hashlib.sha256(payload).hexdigest()[:32]
    return f"RXSET-{digest}"


def _interaction_findings(interactions, item_by_drug_id):
    findings = []
    for interaction in interactions:
        item_a = item_by_drug_id.get(interaction.drug_a_id)
        item_b = item_by_drug_id.get(interaction.drug_b_id)
        if item_a is None or item_b is None:
            continue
        findings.append(
            SafetyFindingResult(
                kind=MedicationSafetyFinding.Kind.INTERACTION,
                severity=interaction.severity,
                blocking=interaction.blocking,
                reason_code=_REASON_INTERACTION,
                interaction_id=interaction.pk,
            )
        )
    return findings


def _dose_not_evaluable_finding(item, reason_code, *, rule=None):
    return SafetyFindingResult(
        kind=MedicationSafetyFinding.Kind.DOSE,
        severity=MedicationSafetyReview.DoseStatus.NOT_EVALUABLE,
        blocking=False,
        reason_code=reason_code,
        request_item_id=item.pk,
        dose_rule_id=rule.pk if rule else None,
    )


def _dose_blocking_finding(item, rule):
    return SafetyFindingResult(
        kind=MedicationSafetyFinding.Kind.DOSE,
        severity=MedicationSafetyReview.DoseStatus.BLOCKED,
        blocking=True,
        reason_code=_REASON_OUTSIDE_RULE,
        request_item_id=item.pk,
        dose_rule_id=rule.pk,
    )


def _age_rule_applies(rule, age_days):
    if rule.min_age_days is not None and age_days < rule.min_age_days:
        return False
    if rule.max_age_days is not None and age_days > rule.max_age_days:
        return False
    return True


def _dose_findings(items, dose_rules, age_days):
    findings = []
    blocked = False
    not_evaluable = False
    rules_by_drug = {}
    for rule in dose_rules:
        rules_by_drug.setdefault(rule.drug_id, []).append(rule)

    for item in items:
        rules = rules_by_drug.get(item.drug_id, [])
        if not rules:
            not_evaluable = True
            findings.append(
                _dose_not_evaluable_finding(item, _REASON_NO_APPLICABLE_RULE)
            )
            continue

        applicable_rule_seen = False
        unresolved_rule_seen = False
        for rule in rules:
            requires_weight = rule.basis in {
                DoseRule.Basis.WEIGHT,
                DoseRule.Basis.AGE_AND_WEIGHT,
            } or rule.per_kg
            if requires_weight:
                not_evaluable = True
                unresolved_rule_seen = True
                findings.append(
                    _dose_not_evaluable_finding(
                        item,
                        _REASON_WEIGHT_UNAVAILABLE,
                        rule=rule,
                    )
                )
                continue

            if age_days is None:
                not_evaluable = True
                unresolved_rule_seen = True
                findings.append(
                    _dose_not_evaluable_finding(
                        item,
                        _REASON_AGE_UNAVAILABLE,
                        rule=rule,
                    )
                )
                continue

            if not _age_rule_applies(rule, age_days):
                continue

            applicable_rule_seen = True
            if item.dose_unit != rule.dose_unit:
                not_evaluable = True
                unresolved_rule_seen = True
                findings.append(
                    _dose_not_evaluable_finding(
                        item,
                        _REASON_UNIT_MISMATCH,
                        rule=rule,
                    )
                )
                continue

            if rule.min_dose is None and rule.max_dose is None:
                not_evaluable = True
                unresolved_rule_seen = True
                findings.append(
                    _dose_not_evaluable_finding(
                        item,
                        _REASON_NO_LIMIT,
                        rule=rule,
                    )
                )
                continue

            below_minimum = rule.min_dose is not None and item.dose < rule.min_dose
            above_maximum = rule.max_dose is not None and item.dose > rule.max_dose
            if below_minimum or above_maximum:
                blocked = True
                findings.append(_dose_blocking_finding(item, rule))

        if not applicable_rule_seen and not unresolved_rule_seen:
            not_evaluable = True
            findings.append(
                _dose_not_evaluable_finding(item, _REASON_NO_APPLICABLE_RULE)
            )

    if blocked:
        status = MedicationSafetyReview.DoseStatus.BLOCKED
    elif not_evaluable:
        status = MedicationSafetyReview.DoseStatus.NOT_EVALUABLE
    else:
        status = MedicationSafetyReview.DoseStatus.PASS
    return status, findings


def evaluate_medication_request_safety(medication_request):
    """Avalia uma prescrição submetida usando somente referências ativas e governadas."""
    if medication_request.status != MedicationRequest.Status.SUBMITTED:
        raise SafetyStateError("A avaliação automática exige prescrição submetida.")

    items = list(
        medication_request.items.select_related("drug").order_by("sequence", "created_at")
    )
    if not items:
        raise SafetyStateError("A avaliação automática exige ao menos um item de prescrição.")

    drug_ids = {item.drug_id for item in items}
    interactions = list(
        Interaction.objects.filter(
            active=True,
            drug_a_id__in=drug_ids,
            drug_b_id__in=drug_ids,
        ).order_by("drug_a_id", "drug_b_id", "reference_version", "id")
    )
    dose_rules = list(
        DoseRule.objects.filter(active=True, drug_id__in=drug_ids).order_by(
            "drug_id",
            "rule_code",
            "reference_version",
            "id",
        )
    )

    if any(not _is_governed_reference(reference) for reference in interactions + dose_rules):
        raise SafetyReferenceError(
            "Há referência farmacêutica ativa sem governança válida."
        )

    item_by_drug_id = {item.drug_id: item for item in items}
    findings = _interaction_findings(interactions, item_by_drug_id)

    age_days = _encounter_age_days(medication_request)
    dose_status, dose_findings = _dose_findings(items, dose_rules, age_days)
    findings.extend(dose_findings)

    blocking_findings = sum(1 for finding in findings if finding.blocking)
    warning_findings = len(findings) - blocking_findings

    return SafetyEvaluation(
        allergy_status=MedicationSafetyReview.AllergyStatus.UNAVAILABLE,
        dose_status=dose_status,
        blocking_findings=blocking_findings,
        warning_findings=warning_findings,
        reference_version=_reference_set_version(interactions, dose_rules),
        findings=tuple(findings),
    )
