"""
MercadoPago HTTP client wrapper.

Change 19 — payments-mercadopago-integration (D-09).

Encapsulates the `mercadopago` Python SDK (v2.3.0+) and exposes:
  - create_preference(): create a Checkout Pro preference (returns init_point).
  - get_payment(): re-query MP API for the real payment status (webhook path).

Design decisions:
  D-09: This wrapper isolates the MP dependency from the service layer.
        Services import `mp_client` (module-level singleton) and call its methods.
        Tests replace mp_client methods via unittest.mock.patch.
  Checkout Pro: create_preference() calls sdk.preference().create() with
                back_urls and external_reference. Returns preference_id +
                init_point + sandbox_init_point.
  X-Idempotency-Key: Passed in `create_preference` to prevent duplicate preferences.
  get_payment(): Still needed — webhook re-queries MP after Checkout Pro payment.

Module-level singleton pattern:
  `mp_client` is instantiated at module import time using `settings.MP_ACCESS_TOKEN`.
  This mirrors the pattern from the spec and avoids per-request SDK initialization.
  Tests patch the instance methods via `unittest.mock.patch.object`.
"""

from __future__ import annotations

from typing import Any


class MercadoPagoAPIError(Exception):
    """Raised when the MercadoPago API returns status >= 400.

    Attributes:
        status_code: HTTP status code from the MP API response.
        detail: Error detail from the response body.
    """

    def __init__(self, message: str, status_code: int = 0, detail: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class MercadoPagoClient:
    """Thin wrapper around the `mercadopago` Python SDK.

    Provides:
      - create_preference(): calls sdk.preference().create() for Checkout Pro.
      - get_payment(): calls sdk.payment().get() for real-time status re-query.

    Both methods raise MercadoPagoAPIError if the SDK response status >= 400.

    Args:
        access_token: MP server-side access token from settings.MP_ACCESS_TOKEN.
    """

    def __init__(self, access_token: str) -> None:
        import mercadopago  # type: ignore[import-untyped]

        self._sdk = mercadopago.SDK(access_token)

    def create_preference(
        self,
        items: list[dict[str, Any]],
        external_reference: str,
        notification_url: str,
        back_urls: dict[str, str],
        idempotency_key: str,
        auto_return: str | None = None,
    ) -> dict[str, Any]:
        """Create a MercadoPago Checkout Pro preference.

        Passes `X-Idempotency-Key` in custom headers to prevent duplicate
        preferences when the request is retried (network failure, timeout, etc.).

        Args:
            items: List of item dicts with title, unit_price, quantity, currency_id.
            external_reference: Pedido UUID as string — returned by MP in webhook.
            notification_url: Full public URL of the IPN webhook endpoint.
            back_urls: Dict with success/pending/failure URL keys.
            idempotency_key: UUID string to prevent duplicate preferences.
            auto_return: Optional "approved" / "all". MercadoPago requires
                back_urls.success to be a publicly reachable HTTPS URL when
                auto_return is set; otherwise the API responds 400
                `invalid_auto_return`. Callers must omit (pass None) for
                local dev with http://localhost back_urls.

        Returns:
            Dict with "id" (preference_id), "init_point", "sandbox_init_point".

        Raises:
            MercadoPagoAPIError: If the MP API returns status >= 400.
        """
        import mercadopago  # type: ignore[import-untyped]

        request_options = mercadopago.config.RequestOptions()
        request_options.custom_headers = {
            "X-Idempotency-Key": idempotency_key,
        }

        preference_data: dict[str, Any] = {
            "items": items,
            "external_reference": external_reference,
            "notification_url": notification_url,
            "back_urls": back_urls,
        }
        if auto_return:
            preference_data["auto_return"] = auto_return

        response = self._sdk.preference().create(preference_data, request_options)

        status_code: int = response.get("status", 0)
        response_body: dict[str, Any] = response.get("response", {})

        if status_code >= 400:
            raise MercadoPagoAPIError(
                f"MercadoPago API error {status_code}: {response_body}",
                status_code=status_code,
                detail=response_body,
            )

        return {
            "id": response_body.get("id"),
            "init_point": response_body.get("init_point"),
            "sandbox_init_point": response_body.get("sandbox_init_point"),
        }

    def get_payment(self, mp_payment_id: int) -> dict[str, Any]:
        """Re-query the MercadoPago API for the real payment status.

        Per RN-PA04 / D-03: always re-query the API — never trust the webhook payload
        alone. This method is called from the webhook handler after HMAC verification.

        Args:
            mp_payment_id: The MercadoPago internal payment ID (from webhook data.id).

        Returns:
            Dict representation of the MP payment object.

        Raises:
            MercadoPagoAPIError: If the MP API returns status >= 400.
        """
        response = self._sdk.payment().get(mp_payment_id)

        status_code: int = response.get("status", 0)
        response_body: dict[str, Any] = response.get("response", {})

        if status_code >= 400:
            raise MercadoPagoAPIError(
                f"MercadoPago API error {status_code}: {response_body}",
                status_code=status_code,
                detail=response_body,
            )

        return response_body


def _create_mp_client() -> MercadoPagoClient:
    """Create the module-level singleton MercadoPagoClient using settings.

    Called once at module import. Uses lazy import to avoid circular deps.
    Tests patch MercadoPagoClient methods via unittest.mock.patch.object.
    """
    from app.core.config import get_settings

    settings = get_settings()
    return MercadoPagoClient(access_token=settings.MP_ACCESS_TOKEN)


# Module-level singleton (D-09). Tests override by patching instance methods.
mp_client: MercadoPagoClient = _create_mp_client()
