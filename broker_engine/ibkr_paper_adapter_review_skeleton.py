"""G6.20 review-only IBKR Paper adapter skeleton.

This is intentionally non-executable. It defines the future adapter interface
while every broker-facing method is hard-disabled.
"""

SKELETON_VERSION = "AURORA_G6_20_IBKR_PAPER_ADAPTER_REVIEW_SKELETON_V1"


class IBKRPaperAdapterReviewSkeleton:
    def __init__(self, review_contract):
        self._review_contract = review_contract

    def describe(self):
        return {
            "skeleton_version": SKELETON_VERSION,
            "mode": "PAPER",
            "host": "127.0.0.1",
            "port": 4002,
            "asset_type": "STK",
            "order_type": "LMT",
            "time_in_force": "DAY",
            "connection_allowed": False,
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "automatic_retry_allowed": False,
            "automatic_cancel_allowed": False,
            "automatic_modify_allowed": False,
            "broker_order_object_allowed": False,
            "broker_request_materialization_allowed": False,
        }

    def connect(self, *args, **kwargs):
        raise RuntimeError("G6_20_CONNECTION_DISABLED")

    def materialize_order_request(self, *args, **kwargs):
        raise RuntimeError("G6_20_REQUEST_MATERIALIZATION_DISABLED")

    def submit_order(self, *args, **kwargs):
        raise RuntimeError("G6_20_ORDER_SUBMISSION_DISABLED")

    def cancel_order(self, *args, **kwargs):
        raise RuntimeError("G6_20_ORDER_CANCELLATION_DISABLED")

    def modify_order(self, *args, **kwargs):
        raise RuntimeError("G6_20_ORDER_MODIFICATION_DISABLED")
