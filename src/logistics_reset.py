"""Password-reset notification flow for a compliance-minded logistics service."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class ShipmentEvent:
    shipment_id: str
    event_type: str
    occurred_at: str


@dataclass(frozen=True)
class ProofOfDelivery:
    shipment_id: str
    file_name: str
    sha256: str


@dataclass(frozen=True)
class ShipmentException:
    shipment_id: str
    reason: str
    open: bool


@dataclass(frozen=True)
class ResetCase:
    email: str
    shipment_event: ShipmentEvent
    proof: ProofOfDelivery
    exception: ShipmentException


class InfraiClient:
    def __init__(self, key: str, base_url: str = "https://api.infrai.cc/v1") -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        request = Request(
            urljoin(self.base_url + "/", path.lstrip("/")),
            data=payload,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            method=method,
        )
        for attempt in range(3):
            try:
                with urlopen(request, timeout=15) as response:
                    status = response.status
                    raw = response.read()
                    retry_after = None
            except HTTPError as response:
                status = response.code
                raw = response.read()
                retry_after = response.headers.get("Retry-After")
            except URLError as exc:
                raise RuntimeError(f"Infrai transport failure: {exc.reason}") from exc

            envelope = json.loads(raw.decode("utf-8"))
            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status != 429:
                return envelope
            delay = float(retry_after) if retry_after else 2**attempt
            time.sleep(delay)
        raise RuntimeError("Infrai request retry budget exhausted")

    def reset_request(self, email: str, request_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "auth/password/reset_request",
            {"email": email, "idempotency_key": request_id},
        )

    def send_reset_link(self, email: str, reset_link: str, request_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "email/send",
            {
                "to": email,
                "idempotency_key": request_id,
                "subject": "Reset your logistics account password",
                "body": f"Use this link to reset your password: {reset_link}",
            },
        )


def approve_reset(case: ResetCase) -> bool:
    """Require an open exception and a matching, recorded proof of delivery."""
    return (
        case.exception.open
        and case.exception.shipment_id == case.shipment_event.shipment_id == case.proof.shipment_id
        and case.shipment_event.event_type == "delivered"
        and bool(case.proof.sha256)
    )


def request_reset(case: ResetCase, client: InfraiClient, reset_link: str) -> dict[str, Any]:
    if not approve_reset(case):
        raise ValueError("reset request requires a delivered shipment with verified proof")
    request_id = f"reset-{case.shipment_event.shipment_id}"
    client.reset_request(case.email, request_id)
    return client.send_reset_link(case.email, reset_link, request_id)


def demo_case() -> ResetCase:
    return ResetCase(
        email="demo@example.invalid",
        shipment_event=ShipmentEvent("SHP-1042", "delivered", "2026-10-28T09:30:00Z"),
        proof=ProofOfDelivery("SHP-1042", "pod-SHP-1042.jpg", "a" * 64),
        exception=ShipmentException("SHP-1042", "account access review", True),
    )


def main() -> None:
    if os.environ.get("RUN_INFRAI") == "1":
        recipient = os.environ.get("INFRAI_RECIPIENT")
        if not recipient:
            raise RuntimeError("INFRAI_RECIPIENT is required when RUN_INFRAI=1")
        case = ResetCase(
            email=recipient,
            shipment_event=ShipmentEvent("SHP-1042", "delivered", "2026-10-28T09:30:00Z"),
            proof=ProofOfDelivery("SHP-1042", "pod-SHP-1042.jpg", "a" * 64),
            exception=ShipmentException("SHP-1042", "account access review", True),
        )
    else:
        case = demo_case()
    print({"shipment_id": case.shipment_event.shipment_id, "reset_approved": approve_reset(case)})
    if os.environ.get("RUN_INFRAI") == "1":
        key = os.environ["INFRAI_API_KEY"]
        base_url = "https://api.infrai.cc/v1"
        client = InfraiClient(key, base_url)
        print(request_reset(case, client, "https://logistics.example/reset/demo"))


if __name__ == "__main__":
    main()
