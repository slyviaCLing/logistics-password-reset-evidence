import pytest

from src.logistics_reset import (
    ProofOfDelivery,
    ResetCase,
    ShipmentEvent,
    ShipmentException,
    approve_reset,
)


def make_case(event_type: str = "delivered", proof_id: str = "SHP-1042") -> ResetCase:
    return ResetCase(
        email="operator@example.com",
        shipment_event=ShipmentEvent("SHP-1042", event_type, "2026-10-28T09:30:00Z"),
        proof=ProofOfDelivery(proof_id, "pod.jpg", "b" * 64),
        exception=ShipmentException("SHP-1042", "account access review", True),
    )


def test_reset_requires_delivery_and_matching_proof() -> None:
    assert approve_reset(make_case()) is True
    assert approve_reset(make_case(event_type="in_transit")) is False
    assert approve_reset(make_case(proof_id="SHP-9999")) is False
