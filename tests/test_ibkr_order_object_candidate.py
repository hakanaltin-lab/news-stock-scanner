"""G8.28 static-only candidate validation tests."""
import json
from pathlib import Path
import unittest
from engines.ibkr_order_object_candidate_review import (
    ENGINE_VERSION,NEXT_GATE,PERMISSION_FLAGS,
    validate_candidate_source,evaluate_order_object_candidate,
)
from engines.ibkr_order_object_design_attestation import (
    ENGINE_VERSION as UPSTREAM_ENGINE,NEXT_GATE as UPSTREAM_NEXT_GATE,
)
ROOT=Path(__file__).resolve().parents[1]
def source():
    return (ROOT/"broker_engine/ibkr_order_object_materializer_candidate.py").read_text()
def upstream():
    return {
        "engine":UPSTREAM_ENGINE,"status":"VERIFIED","verified":True,
        "order_object_design_independently_attested":True,
        "reason":"INDEPENDENT_IBKR_ORDER_OBJECT_DESIGN_ATTESTATION_VERIFIED",
        "checks":{"signature_valid":True,"design_bound":True},
        "review_id":"77777777-7777-4777-8777-777777777777",
        "reviewer_id":"independent-reviewer",
        "design_sha256":"1"*64,"review_request_sha256":"2"*64,
        "upstream_attestation_result_sha256":"3"*64,"attestation_sha256":"4"*64,
        **{name:False for name in PERMISSION_FLAGS},
        "next_gate":UPSTREAM_NEXT_GATE,
    }
class CandidateTests(unittest.TestCase):
    def test_valid_candidate_is_not_executable(self):
        r=evaluate_order_object_candidate(upstream(),source())
        self.assertEqual(r["engine"],ENGINE_VERSION)
        self.assertEqual(r["status"],"NON_EXECUTABLE_ORDER_OBJECT_CANDIDATE_VALIDATED")
        self.assertEqual(r["next_gate"],NEXT_GATE)
        for name in PERMISSION_FLAGS:self.assertIs(r[name],False)
    def test_unverified_attestation_blocks(self):
        value=upstream();value["verified"]=False
        self.assertEqual(evaluate_order_object_candidate(value,source())["status"],"BLOCKED")
    def test_permission_regression_blocks(self):
        value=upstream();value["broker_order_object_allowed"]=True
        self.assertEqual(evaluate_order_object_candidate(value,source())["status"],"BLOCKED")
    def test_import_injection_blocks(self):
        self.assertFalse(validate_candidate_source(source()+"\nimport ibapi\n")[0])
    def test_order_creation_becoming_live_blocks(self):
        replaced=source().replace('raise RuntimeError("G8_28_ORDER_CREATION_DISABLED")',"return True")
        self.assertFalse(validate_candidate_source(replaced)[0])
    def test_submit_enablement_blocks(self):
        replaced=source().replace('raise RuntimeError("G8_28_ORDER_SUBMISSION_DISABLED")',"return True")
        self.assertFalse(validate_candidate_source(replaced)[0])
    def test_dynamic_import_blocks(self):
        self.assertFalse(validate_candidate_source(source()+"\n__import__('ibapi')\n")[0])
    def test_permission_literal_tamper_blocks(self):
        tampered=source().replace('"live_execution_allowed": False','"live_execution_allowed": True')
        self.assertFalse(validate_candidate_source(tampered)[0])
    def test_duplicate_method_blocks(self):
        tampered=source()+"\n    def submit_order(self, *args, **kwargs):\n        return True\n"
        self.assertFalse(validate_candidate_source(tampered)[0])
    def test_extra_attribute_blocks(self):
        tampered=source().replace('self._design_attestation_sha256 = design_attestation_sha256','self._design_attestation_sha256 = design_attestation_sha256\n        self.enabled = True')
        self.assertFalse(validate_candidate_source(tampered)[0])
    def test_extra_attestation_field_blocks(self):
        value=upstream();value["raw_account_id"]="DU12345"
        r=evaluate_order_object_candidate(value,source())
        self.assertEqual(r["status"],"BLOCKED")
        self.assertNotIn("DU12345",json.dumps(r))
if __name__=="__main__":unittest.main()
