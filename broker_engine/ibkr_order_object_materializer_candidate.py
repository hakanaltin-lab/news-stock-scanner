"""G8.28 review-only candidate. NEVER import or execute during approval.

No IBKR imports, objects, network calls or actual broker functions.
All exposed methods are fixed hard blocks.
"""

CANDIDATE_VERSION = "AURORA_G8_28_ORDER_OBJECT_CANDIDATE_V1"
DESIGN_ID = "AURORA_G8_25_IBKR_ORDER_OBJECT_MATERIALIZER_DESIGN_V1"


class IBKROrderObjectMaterializerCandidate:
    def __init__(self, design_attestation_sha256):
        self._design_attestation_sha256 = design_attestation_sha256

    def describe(self):
        return {
            "candidate_version": CANDIDATE_VERSION,
            "design_id": DESIGN_ID,
            "non_executable": True,
            "broker_mode": "PAPER",
            "host": "127.0.0.1",
            "port": 4002,
            "asset_type": "STK",
            "order_type": "LMT",
            "time_in_force": "DAY",
            "transmit": False,
            "ibkr_import_allowed": False,
            "network_allowed": False,
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
        raise RuntimeError("G8_28_CONNECTION_DISABLED")

    def create_contract(self, *args, **kwargs):
        raise RuntimeError("G8_28_CONTRACT_CREATION_DISABLED")

    def create_order(self, *args, **kwargs):
        raise RuntimeError("G8_28_ORDER_CREATION_DISABLED")

    def submit_order(self, *args, **kwargs):
        raise RuntimeError("G8_28_ORDER_SUBMISSION_DISABLED")

    def cancel_order(self, *args, **kwargs):
        raise RuntimeError("G8_28_CANCELLATION_DISABLED")

    def modify_order(self, *args, **kwargs):
        raise RuntimeError("G8_28_MODIFICATION_DISABLED")
