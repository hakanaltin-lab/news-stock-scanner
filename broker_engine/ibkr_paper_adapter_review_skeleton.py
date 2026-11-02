"""G8.13 review-only IBKR Paper adapter interface.

This module is intentionally non-executable. It contains no broker import and
all broker-facing methods are hard-disabled until later independent review
gates explicitly replace this review skeleton.
"""

SKELETON_VERSION = "AURORA_G8_13_IBKR_PAPER_ADAPTER_REVIEW_SKELETON_V1"


class IBKRPaperAdapterReviewSkeleton:
    def __init__(self, runtime_prerequisite_sha256):
        self._runtime_prerequisite_sha256 = runtime_prerequisite_sha256

    def describe(self):
        return {
            "skeleton_version": SKELETON_VERSION,
            "review_only": True,
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
        raise RuntimeError("G8_13_CONNECTION_DISABLED")

    def materialize_order_request(self, *args, **kwargs):
        raise RuntimeError("G8_13_REQUEST_MATERIALIZATION_DISABLED")

    def submit_order(self, *args, **kwargs):
        raise RuntimeError("G8_13_ORDER_SUBMISSION_DISABLED")

    def cancel_order(self, *args, **kwargs):
        raise RuntimeError("G8_13_ORDER_CANCELLATION_DISABLED")

    def modify_order(self, *args, **kwargs):
        raise RuntimeError("G8_13_ORDER_MODIFICATION_DISABLED")
