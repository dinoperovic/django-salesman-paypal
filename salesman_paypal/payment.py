from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, TypeVar

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import URLPattern, URLResolver, path, reverse
from django.utils.decorators import method_decorator
from django.utils.text import Truncator
from paypalcheckoutsdk.core import (
    LiveEnvironment,
    PayPalEnvironment,
    PayPalHttpClient,
    SandboxEnvironment,
)
from paypalcheckoutsdk.orders import OrdersCaptureRequest, OrdersCreateRequest
from paypalcheckoutsdk.payments import CapturesRefundRequest
from paypalhttp import HttpError as PayPalHttpError
from paypalhttp.http_response import Result
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from salesman.basket.models import BaseBasket
from salesman.checkout.payment import PaymentError, PaymentMethod
from salesman.core.utils import get_salesman_model
from salesman.orders.models import BaseOrder, BaseOrderPayment

from .conf import app_settings

logger = logging.getLogger(__name__)

BasketOrOrder = TypeVar("BasketOrOrder", BaseBasket, BaseOrder)


class PayPalPayment(PaymentMethod):  # type: ignore
    """
    PayPal payment method.
    """

    identifier = "paypal"
    label = app_settings.SALESMAN_PAYPAL_PAYMENT_LABEL

    def get_urls(self) -> list[URLPattern | URLResolver]:
        """
        Register PayPal views.
        """
        return [
            path("return/", self.return_view, name="paypal-return"),
            path("cancel/", self.cancel_view, name="paypal-cancel"),
            path("capture/<order_id>/", self.capture_view, name="paypal-capture"),
        ]

    def basket_payment(
        self,
        basket: BaseBasket,
        request: HttpRequest,
    ) -> dict[str, Any]:
        """
        Create order for Basket.
        """
        return self.process_payment(basket, request)

    def order_payment(
        self,
        order: BaseOrder,
        request: HttpRequest,
    ) -> dict[str, Any]:
        """
        Pay for for an existing Order.
        """
        return self.process_payment(order, request)

    def process_payment(
        self,
        obj: BasketOrOrder,
        request: HttpRequest,
    ) -> dict[str, Any]:
        """
        Processs payment for either the Basket or Order.
        """
        try:
            paypal_order = self.create_paypal_order(obj, request)
            data: dict[str, Any] = paypal_order.dict()
            return data
        except PayPalHttpError as e:
            logger.error(e)
            raise PaymentError(str(e))

    def create_paypal_order(self, obj: BasketOrOrder, request: HttpRequest) -> Result:
        """
        Create a PayPal order and return the result.
        """
        paypal_request = OrdersCreateRequest()
        paypal_request.prefer("return=representation")
        paypal_request.request_body(self.get_paypal_order_data(obj, request))
        paypal_response = self.get_paypal_client().execute(paypal_request)
        return paypal_response.result

    def get_paypal_order_data(
        self,
        obj: BasketOrOrder,
        request: HttpRequest,
    ) -> dict[str, Any]:
        """
        Returns PayPal order create request data.

        See available data to be set in PayPal:
        https://developer.paypal.com/api/orders/v2/#orders-create-request-body
        """
        return {
            "intent": "CAPTURE",
            "payer": self.get_paypal_payer_data(obj, request),
            "purchase_units": [self.get_paypal_purchase_unit_data(obj, request)],
            "application_context": self.get_paypal_app_context_data(obj, request),
        }

    def get_paypal_payer_data(
        self,
        obj: BasketOrOrder,
        request: HttpRequest,
    ) -> dict[str, Any]:
        """
        Returns PayPal payer data.

        See available data to be set in PayPal:
        https://developer.paypal.com/api/orders/v2/#definition-payer
        """
        if not obj.user:
            return {"email_address": getattr(obj, "email", obj.extra["email"])}

        return {
            "email_address": obj.user.email or None,
            "name": {
                "given_name": obj.user.first_name or obj.user.get_username(),
                "surname": obj.user.last_name or None,
            },
        }

    def get_paypal_purchase_unit_data(
        self,
        obj: BasketOrOrder,
        request: HttpRequest,
    ) -> dict[str, Any]:
        """
        Returns PayPal order purchase unit data.

        See available data to be set in PayPal:
        https://developer.paypal.com/api/orders/v2/#definition-purchase_unit_request
        """
        currency = self.get_currency(request)

        return {
            "amount": {
                "currency_code": currency,
                "value": str(obj.total),
                "breakdown": {
                    "item_total": {
                        "currency_code": currency,
                        "value": str(obj.total),
                    },
                },
            },
            "custom_id": self.get_reference(obj),
            "items": self.get_paypal_items_data(obj, request),
            "shipping": self.get_paypal_shipping_data(obj, request),
        }

    def get_paypal_items_data(
        self,
        obj: BasketOrOrder,
        request: HttpRequest,
    ) -> list[dict[str, Any]]:
        """
        Returns PayPal order items data.

        See available data to be set in PayPal:
        https://developer.paypal.com/api/orders/v2/#definition-item
        """

        return [
            {
                "name": f"Purchase {len(obj.get_items())} items",
                "unit_amount": {
                    "currency_code": self.get_currency(request),
                    "value": str(obj.total),
                },
                "quantity": "1",
                "description": Truncator(
                    ", ".join(
                        [f"{item.quantity}x {item.name}" for item in obj.get_items()]
                    )
                ).chars(127),
            }
        ]

    def get_paypal_shipping_data(
        self,
        obj: BasketOrOrder,
        request: HttpRequest,
    ) -> dict[str, Any]:
        """
        Returns PayPal order shipping data.

        See available data to be set in PayPal:
        https://developer.paypal.com/api/orders/v2/#definition-shipping_detail
        """
        return {
            "name": {
                "full_name": obj.user.get_full_name() if obj.user else None,
            }
        }

    def get_paypal_app_context_data(
        self,
        obj: BasketOrOrder,
        request: HttpRequest,
    ) -> dict[str, Any]:
        """
        Returns PayPal order application context data.

        See available data to be set in PayPal:
        https://developer.paypal.com/api/orders/v2/#definition-order_application_context
        """
        return {
            "return_url": request.build_absolute_uri(reverse("paypal-return")),
            "cancel_url": request.build_absolute_uri(reverse("paypal-cancel")),
        }

    def refund_payment(self, payment: BaseOrderPayment) -> bool:
        """
        Refund payment on PayPal.
        """
        paypal_request = CapturesRefundRequest(payment.transaction_id)
        paypal_request.prefer("return=minimal")
        try:
            self.get_paypal_client().execute(paypal_request)
        except PayPalHttpError as e:
            logger.error(e)
            return False
        return True

    def get_currency(self, request: HttpRequest) -> str:
        """
        Returns ISO currency for the given request.
        """
        return app_settings.SALESMAN_PAYPAL_DEFAULT_CURRENCY.upper()

    def get_reference(self, obj: BasketOrOrder) -> str:
        """
        Returns a reference ID for the given object used to identify the PayPal order.
        """
        if isinstance(obj, BaseBasket):
            return f"basket_{obj.id}"
        return f"order_{obj.id}"

    @classmethod
    def parse_reference(cls, reference: str) -> tuple[str | None, str | None]:
        """
        Parses the reference ID returning the object kind and ID.
        """
        try:
            kind, id = reference.split("_")
            assert kind in ("basket", "order")
            return kind, id
        except Exception:
            return None, None

    @classmethod
    def get_paypal_environment(cls) -> PayPalEnvironment:
        """
        Returns environment class used in PayPal client.
        """
        environment_class = (
            SandboxEnvironment
            if app_settings.SALESMAN_PAYPAL_SANDBOX_MODE
            else LiveEnvironment
        )
        return environment_class(
            client_id=app_settings.SALESMAN_PAYPAL_CLIENT_ID,
            client_secret=app_settings.SALESMAN_PAYPAL_CLIENT_SECRET,
        )

    @classmethod
    def get_paypal_client(cls) -> PayPalHttpClient:
        """
        Returns PayPal http API client.
        """
        return PayPalHttpClient(cls.get_paypal_environment())

    @classmethod
    def return_view(cls, request: HttpRequest) -> HttpResponse:
        """
        Handle approved payment on PayPal.
        """
        if app_settings.SALESMAN_PAYPAL_RETURN_URL:
            return redirect(app_settings.SALESMAN_PAYPAL_RETURN_URL)
        return render(request, "salesman_paypal/return.html")

    @classmethod
    def cancel_view(cls, request: HttpRequest) -> HttpResponse:
        """
        Handle cancelled payment on PayPal.
        """
        if app_settings.SALESMAN_PAYPAL_CANCEL_URL:
            return redirect(app_settings.SALESMAN_PAYPAL_CANCEL_URL)
        return render(request, "salesman_paypal/cancel.html")

    @classmethod
    @method_decorator(api_view(["POST"]))  # type: ignore
    @method_decorator(renderer_classes([JSONRenderer]))  # type: ignore
    def capture_view(cls, request: Request, order_id: int) -> Response:
        """
        Order capture view.
        """
        try:
            paypal_request = OrdersCaptureRequest(order_id)
            paypal_request.prefer("return=representation")
            paypal_response = cls.get_paypal_client().execute(paypal_request)
        except PayPalHttpError as e:
            logger.error(e)
            error = json.loads(e.message)
            return Response(error, status=400)

        return cls.capture_paypal_order(request, paypal_response.result)

    @classmethod
    def capture_paypal_order(cls, request: Request, paypal_order: Result) -> Response:
        """
        Fulfill order from an approved PayPal order.
        """
        Basket = get_salesman_model("Basket")
        Order = get_salesman_model("Order")

        paypal_purchase_unit = paypal_order.purchase_units[0]
        kind, id = cls.parse_reference(paypal_purchase_unit.custom_id)
        if kind == "basket":
            try:
                basket = Basket.objects.get(id=id)
            except BaseBasket.DoesNotExist:
                logger.error(f"Missing basket: {id}")
                return Response({"detail": "Missing basket"}, status=400)

            kwargs = {"status": app_settings.SALESMAN_PAYPAL_PAID_STATUS}
            order = Order.objects.create_from_basket(basket, request, **kwargs)
            basket.delete()
        elif kind == "order":
            try:
                order = Order.objects.get(id=id)
            except BaseOrder.DoesNotExist:
                logger.error(f"Missing order: {id}")
                return Response({"detail": "Missing order"}, status=400)
        else:
            logger.error(f"Invalid paypal reference: {paypal_order.id}")
            return Response({"detail": "Invalid paypal reference"}, status=400)

        # Capture payment on order.
        paypal_capture = paypal_purchase_unit.payments.captures[0]
        order.pay(
            amount=Decimal(paypal_capture.amount.value),
            transaction_id=paypal_capture.id,
            payment_method=cls.identifier,
        )

        logger.info(f"Order fulfilled: {order.ref}")
        return Response(paypal_order.dict())
