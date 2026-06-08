"""
Pydantic v2 schemas for the pagos module.

Change 19 — payments-mercadopago-integration (Checkout Pro migration).

Schemas:
  PagoCreateRequest: body for POST /api/v1/pagos (Checkout Pro start)
  PagoResponse: response for POST /api/v1/pagos and GET /api/v1/pagos/{pedido_id}/latest

Design decisions:
  - Checkout Pro flow: PagoCreateRequest carries pedido_id + idempotency_key only.
    No card data — tokenization is done by MP hosted checkout page.
  - PagoResponse includes preference_id, init_point, sandbox_init_point so the
    frontend can redirect the user to the MP hosted checkout page.
  - mp_payment_id is NULL until the webhook fires and assigns the real MP payment ID.
  - monto serialized as string (Decimal → str) to avoid float precision issues.
  - from_attributes=True: allows model_validate(pago_orm) to work directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class PagoCreateRequest(BaseModel):
    """Request body for POST /api/v1/pagos.

    Initiates a MercadoPago Checkout Pro flow for the given order.

    Fields:
      pedido_id: UUID of the order being paid.
      idempotency_key: Client-supplied idempotency key (min 8 chars).
                       Prevents duplicate preference creation on retries.
    """

    model_config = ConfigDict(from_attributes=True)

    pedido_id: uuid.UUID
    idempotency_key: str = Field(min_length=8)


class PagoResponse(BaseModel):
    """Response for POST /api/v1/pagos and GET /api/v1/pagos/{pedido_id}/latest.

    Serializes the Pago ORM row into a JSON-safe dict.
    monto is serialized as a string to preserve Decimal precision ("150.00").

    Checkout Pro fields:
      preference_id: MP preference ID. NULL for rows created before migration.
      init_point: Live MP hosted checkout URL.
      sandbox_init_point: Sandbox MP hosted checkout URL.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pedido_id: uuid.UUID
    mp_payment_id: Optional[int] = None
    mp_preference_id: Optional[str] = None
    mp_status: str
    mp_status_detail: Optional[str] = None
    preference_id: Optional[str] = None
    init_point: Optional[str] = None
    sandbox_init_point: Optional[str] = None
    idempotency_key: str
    external_reference: str
    monto: Optional[Decimal] = None
    created_at: datetime

    @field_serializer("monto")
    def serialize_monto(self, value: Optional[Decimal]) -> Optional[str]:
        """Serialize Decimal monto as a string to preserve precision.

        Returns "150.00" instead of 150.0 (float) or 150 (int).
        Returns None if monto is None.
        """
        if value is None:
            return None
        return str(value)


class PagoReconcileRequest(BaseModel):
    """Request body for POST /api/v1/pagos/reconcile.

    Frontend-driven fallback: when MP webhook can't reach the local backend
    (typical in dev), the CheckoutReturnPage calls this endpoint with the
    payment_id MP appended to the back_url.

    Fields:
      pedido_id: UUID of the order whose payment must be reconciled.
      payment_id: MercadoPago payment ID from the back_url query param.
                  Required (lookup-by-external_reference not implemented).
      external_reference: Echo of external_reference from MP back_url; if
                          provided it must equal str(pedido_id).
    """

    model_config = ConfigDict(from_attributes=True)

    pedido_id: uuid.UUID
    payment_id: Optional[int] = None
    external_reference: Optional[str] = None


class PagoReconcileResponse(BaseModel):
    """Response for POST /api/v1/pagos/reconcile.

    Reports the post-reconcile state so the frontend can decide whether to
    stop polling (approved/rejected) or keep showing the spinner (pending).
    """

    status: str  # always "ok" when the call succeeds
    mp_status: str
    pedido_estado: str
    already_processed: bool = False
