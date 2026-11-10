"""Alpaca PAPER adapter stub. Disabled. It places no orders and makes no network calls.

To use it later, the operator would set ALPACA_PAPER_KEY and ALPACA_PAPER_SECRET himself and flip
broker.enabled in config. This module never asks for keys and refuses non-paper endpoints.
"""
import os

PAPER_URL = "https://paper-api.alpaca.markets"


class AlpacaPaperStub:
    enabled = False

    def __init__(self, base_url=PAPER_URL):
        if "paper" not in base_url:
            raise PermissionError("Only the Alpaca paper endpoint is allowed.")
        self.base_url = base_url
        self.has_keys = bool(os.environ.get("ALPACA_PAPER_KEY") and os.environ.get("ALPACA_PAPER_SECRET"))

    def submit_order(self, *a, **k):
        raise NotImplementedError("Alpaca adapter is a disabled stub in v1. No orders are placed.")
