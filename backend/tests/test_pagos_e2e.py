"""
Sandbox e2e integration test for MercadoPago payment creation.

Change 19 — payments-mercadopago-integration.
Task 18.6 — opt-in sandbox test.

This test is opt-in: it only runs when MP_SANDBOX_ACCESS_TOKEN is set in the environment.
It validates the MP API call path with real sandbox credentials.

Full e2e webhook flow coverage (ngrok + IPN) is deferred to Change 25 (test_pagos domain).
This test validates only the MP API call path with real sandbox credentials.

Usage:
    MP_SANDBOX_ACCESS_TOKEN=TEST-xxxx pytest backend/tests/test_pagos_e2e.py -m e2e -v

Sandbox cards (from Integrador §8.3):
    5031 7557 3453 0604 — Mastercard (approved)
    4509 9535 6623 3704 — Visa (approved)
"""

from __future__ import annotations

import os
import uuid

import pytest


@pytest.mark.e2e
@pytest.mark.skipif(
    not os.getenv("MP_SANDBOX_ACCESS_TOKEN"),
    reason="MP sandbox credentials not set. Set MP_SANDBOX_ACCESS_TOKEN to run this test.",
)
def test_mercadopago_sandbox_integration():
    """Validate MercadoPago API call path using real sandbox credentials.

    Full e2e webhook flow coverage is deferred to Change 25 (test_pagos domain).
    This test validates only the MP API call path with real sandbox credentials.

    Preconditions:
        - MP_SANDBOX_ACCESS_TOKEN env var is set to a valid TEST- access token.
        - The sandbox environment is reachable.

    Assertions:
        - mp_payment_id is a valid integer.
        - mp_status is one of {"pending", "approved", "in_process"}.

    Note: Sandbox card tokenization requires a frontend step (CardPayment widget).
    This test skips actual card tokenization and instead calls create_payment with
    a pre-tokenized sandbox card token. In practice, the sandbox token must be
    obtained via the MP SDK frontend before running this test.
    """
    from app.integrations.mercadopago_client import MercadoPagoClient

    sandbox_token = os.environ["MP_SANDBOX_ACCESS_TOKEN"]
    client = MercadoPagoClient(access_token=sandbox_token)

    # Use a pre-tokenized sandbox card token.
    # Obtain via MP CardPayment widget using card: 5031 7557 3453 0604
    # This value must be provided as env var for the test to work end-to-end.
    card_token = os.getenv("MP_SANDBOX_CARD_TOKEN")
    if not card_token:
        pytest.skip(
            "MP_SANDBOX_CARD_TOKEN not set. Tokenize a sandbox card first and set this env var."
        )

    pedido_id = str(uuid.uuid4())
    idempotency_key = str(uuid.uuid4())

    result = client.create_payment(
        idempotency_key=idempotency_key,
        card_token=card_token,
        pedido_id=pedido_id,
        amount=100.00,
        payment_method_id="master",
        installments=1,
    )

    assert isinstance(result["id"], int), f"mp_payment_id is not an integer: {result['id']!r}"
    assert result["status"] in {
        "pending",
        "approved",
        "in_process",
    }, f"Unexpected mp_status: {result['status']!r}"
