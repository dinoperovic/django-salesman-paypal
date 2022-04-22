from __future__ import annotations

from typing import Any


class AppSettings:
    @property
    def SALESMAN_PAYPAL_CLIENT_ID(self) -> str:
        """
        PayPal client ID.
        """
        return str(self._required_setting("SALESMAN_PAYPAL_CLIENT_ID"))

    @property
    def SALESMAN_PAYPAL_CLIENT_SECRET(self) -> str:
        """
        PayPal client secret.
        """
        return str(self._required_setting("SALESMAN_PAYPAL_CLIENT_SECRET"))

    @property
    def SALESMAN_PAYPAL_SANDBOX_MODE(self) -> bool:
        """
        Enable PayPal sandbox mode for development.
        """
        return bool(self._setting("SALESMAN_PAYPAL_SANDBOX_MODE", False))

    @property
    def SALESMAN_PAYPAL_PAYMENT_LABEL(self) -> str:
        """
        Payment method label used when displayed in the basket.
        """
        return str(self._setting("SALESMAN_PAYPAL_PAYMENT_LABEL", "Pay with PayPal"))

    @property
    def SALESMAN_PAYPAL_DEFAULT_CURRENCY(self) -> str:
        """
        Default ISO currency used for payments, must be set to a valid PayPal currency.
        https://developer.paypal.com/docs/reports/reference/paypal-supported-currencies/
        """
        return str(self._setting("SALESMAN_PAYPAL_DEFAULT_CURRENCY", "USD"))

    @property
    def SALESMAN_PAYPAL_RETURN_URL(self) -> str:
        """
        URL to redirect to when PayPal payment is approved.
        """
        return str(self._setting("SALESMAN_PAYPAL_RETURN_URL", default=""))

    @property
    def SALESMAN_PAYPAL_CANCEL_URL(self) -> str:
        """
        URL to redirect to when PayPal payment is cancelled.
        """
        return str(self._setting("SALESMAN_PAYPAL_CANCEL_URL", default=""))

    @property
    def SALESMAN_PAYPAL_PAID_STATUS(self) -> str:
        """
        Default paid status for fullfiled orders.
        """
        return str(self._setting("SALESMAN_PAYPAL_PAID_STATUS", "PROCESSING"))

    def _setting(self, name: str, default: Any = None) -> Any:
        from django.conf import settings

        return getattr(settings, name, default)

    def _required_setting(self, name: str) -> Any:
        value = self._setting(name)
        if not value:
            self._error(f"Missing `{name}` in your settings.")
        return value

    def _error(self, message: str | Exception) -> None:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(message)


app_settings = AppSettings()
