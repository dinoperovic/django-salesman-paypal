# Salesman PayPal

[![PyPI](https://img.shields.io/pypi/v/django-salesman-paypal)](https://pypi.org/project/django-salesman-paypal/)
[![Test](https://github.com/dinoperovic/django-salesman-paypal/actions/workflows/test.yml/badge.svg)](https://github.com/dinoperovic/django-salesman-paypal/actions/workflows/test.yml)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-salesman-paypal)](https://pypi.org/project/django-salesman-paypal/)
[![PyPI - Django Version](https://img.shields.io/pypi/djversions/django-salesman-paypal)](https://pypi.org/project/django-salesman-paypal/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[PayPal](https://www.paypal.com/) payment integration for [Salesman](https://github.com/dinoperovic/django-salesman).

## Installation

Install the package using pip:

```bash
pip install django-salesman-paypal
```

Add to your setting file:

```python
INSTALLED_APPS = ['salesman_paypal']
SALESMAN_PAYMENT_METHODS = ['salesman_paypal.payment.PayPalPayment']
SALESMAN_PAYPAL_CLIENT_ID = '<paypal-client-id>'
SALESMAN_PAYPAL_CLIENT_SECRET = '<paypal-client-secret>'
SALESMAN_PAYPAL_SANDBOX_MODE = True  # Disable in production
```

### Usage guide

To use this payment on your website, checkout the official PayPal server [integration guide](https://developer.paypal.com/demo/checkout/#/pattern/server).

See `example` directory in this repository for integration example using JavaScript.

### Additional settings

Optional additional settings that you can override:

```python
# Payment method label used when displayed in the basket.
SALESMAN_PAYPAL_PAYMENT_LABEL = 'Pay with PayPal'

# Default PayPal currency used for payments (https://developer.paypal.com/docs/reports/reference/paypal-supported-currencies/)
SALESMAN_PAYPAL_DEFAULT_CURRENCY = 'USD'

# URL to redirect to when PayPal payment is approved.
SALESMAN_PAYPAL_RETURN_URL = '/paypal/return/'

# URL to redirect to when PayPal payment is cancelled.
SALESMAN_PAYPAL_CANCEL_URL = '/paypal/cancel/'

# Default paid status for fullfiled orders.
SALESMAN_PAYPAL_PAID_STATUS = 'PROCESSING'
```

## Advanced usage

To gain more control feel free to extend the `PayPalPayment` class with your custom functionality:

```python
# shop/payment.py
from salesman_paypal.payment import PayPalPayment
from salesman_paypal.conf import app_settings

class MyPayPalPayment(StripePayment):
    def get_paypal_payer_data(self, obj, request):
        # https://developer.paypal.com/api/orders/v2/#definition-payer
        data = super().get_paypal_payer_data(obj, request)
        if obj.user and obj.user.birth_date:
            data['birth_date'] = obj.user.birth_date.strftime('%Y-%m-%d')
        return data

    def get_currency(self, request):
        currency = request.GET.get('currency', None)
        # Check currency is valid for PayPal...
        return currency or app_settings.SALESMAN_PAYPAL_DEFAULT_CURRENCY
```

Make sure to use your payment method in `settings.py`:

```python
SALESMAN_PAYMENT_METHODS = ['shop.payment.MyPayPalPayment']
```

The `PayPalPayment` class is setup with extending in mind, feel free to explore other methods.
