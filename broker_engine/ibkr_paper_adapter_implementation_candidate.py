"""G8.19 non-executable IBKR Paper adapter implementation candidate.

This file is a review candidate only. It contains no broker imports, creates no
IBKR request/order objects, opens no connection, and all broker-facing methods
remain hard-disabled.
"""

CANDIDATE_VERSION = "AURORA_G8_19_IBKR_PAPER_ADAPTER_IMPLEMENTATION_CANDIDATE_V1"
DESIGN_ID = "AURORA_G8_16_IBKR_PAPER_ADAPTER_IMPLEMENTATION_DESIGN_V1"


class IBKRPaperAdapterImplementationCandidate:
    def __init__(self, design_attestation_sha256):
        self._design_attestation_sha256 = design_attestation_sha256

    def describe(self):
        return {
            "candidate_version": CANDIDATE_VERSION,
            "design_id": DESIGN_ID,
            "implementation_candidate": True,
            "non_executable": True,
            "mode": "PAPER",
            "host": "127.0.0.1",
            "port": 4002,
            "asset_type": "STK",
            "order_type": "LMT",
            "time_in_force": "DAY",
            "market_order_allowed": False,
            "short_selling_allowed": False,
            "fractional_quantity_allowed": False,
            "credentials_allowed": False,
            "raw_account_id_allowed": False,
            "implementation_allowed": False,
            "connection_allowed": False,
            "broker_request_materialization_allowed": False,
            "broker_order_object_allowed": False,
            "automatic_retry_allowed": False,
            "automatic_cancel_allowed": False,
            "automatic_modify_allowed": False,
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "automatic_promotion_allowed": False,
            "real_money_trading_allowed": False,
        }

    def connect(self, *args, **kwargs):
        raise RuntimeError("G8_19_CONNECTION_DISABLED")

    def materialize_order_request(self, *args, **kwargs):
        raise RuntimeError("G8_19_REQUEST_MATERIALIZATION_DISABLED")

    def submit_order(self, *args, **kwargs):
        raise RuntimeError("G8_19_ORDER_SUBMISSION_DISABLED")

    def cancel_order(self, *args, **kwargs):
        raise RuntimeError("G8_19_ORDER_CANCELLATION_DISABLED")

    def modify_order(self, *args, **kwargs):
        raise RuntimeError("G8_19_ORDER_MODIFICATION_DISABLED")
