import re
from pathlib import Path

from django.test import SimpleTestCase
from apps.clinical.adt.events import ADT_EVENT_TYPES
from apps.clinical.adt.urls import urlpatterns as adt_urlpatterns


CONTRACT_PATH = (
    Path(__file__).resolve().parents[4]
    / "specs"
    / "002-adt"
    / "contracts"
    / "events.asyncapi.yaml"
)


class AdtContractTests(SimpleTestCase):
    def test_asyncapi_event_names_match_runtime_allowlist(self):
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        declared = set(
            re.findall(r"^\s+name:\s+([a-z]+\.[a-z_.]+)\s*$", contract, re.MULTILINE)
        )

        self.assertSetEqual(declared, ADT_EVENT_TYPES)

    def test_websocket_contract_matches_minimized_browser_payload(self):
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("address: /ws/clinical/adt/bed-map/", contract)

        payload_section = contract.split("BedMapInvalidationPayload:", 1)[1].split(
            "\n  messages:", 1
        )[0]
        for forbidden_field in ("encounter_id", "admission_id", "occupancy_id"):
            self.assertNotIn(forbidden_field, payload_section)

        for required_field in (
            "event_id",
            "event_type",
            "occurred_at",
            "bed_id",
            "location_id",
            "state",
        ):
            self.assertIn(required_field, payload_section)

    def test_adt_does_not_define_public_api_routes(self):
        routes = {str(pattern.pattern) for pattern in adt_urlpatterns}
        self.assertFalse(any(route.startswith("api/") for route in routes))
