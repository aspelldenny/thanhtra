import os

STRIPE_API_KEY = os.environ["STRIPE_API_KEY"]


def get_payment_key():
    return STRIPE_API_KEY
