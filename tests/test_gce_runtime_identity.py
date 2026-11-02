"""G7.7 tests for fixed link-local GCE runtime identity validation."""

import inspect
import unittest

import engines.gce_runtime_identity as identity


class GCERuntimeIdentityTests(unittest.TestCase):
    def evaluate(self, **overrides):
        values = {
            "project_id":
            "project-ce9773ef-6814-469c-92b",

            "instance_name":
            "aurora-trading-vps",

            "zone_path":
            "projects/123/zones/europe-west3-a",

            "instance_id":
            "1234567890123456789",
        }

        values.update(
            overrides
        )

        return identity.evaluate_gce_runtime_identity(
            **values
        )

    def test_exact_approved_identity_passes(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "VERIFIED",
        )
        self.assertTrue(
            result["verified"]
        )
        self.assertEqual(
            result["zone"],
            "europe-west3-a",
        )

    def test_wrong_project_instance_or_zone_blocks(self):
        cases = (
            (
                {
                    "project_id":
                    "different-project",
                },
                "project_id_matches_approved_project",
            ),
            (
                {
                    "instance_name":
                    "clone-vps",
                },
                "instance_name_matches_approved_vps",
            ),
            (
                {
                    "zone_path":
                    "projects/123/zones/us-central1-a",
                },
                "zone_path_valid",
            ),
        )

        for overrides, failure in cases:
            with self.subTest(
                failure=failure
            ):
                result = self.evaluate(
                    **overrides
                )

                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assertIn(
                    failure,
                    result["failure_reasons"],
                )

    def test_instance_id_must_be_nonzero_numeric_identity(self):
        for value in (
            "",
            "0",
            "000123456",
            "abc123456",
            "-123456",
            "12345",
        ):
            with self.subTest(
                value=value
            ):
                result = self.evaluate(
                    instance_id=value
                )

                self.assertIn(
                    "instance_id_valid",
                    result["failure_reasons"],
                )

    def test_metadata_reader_has_fixed_link_local_no_proxy_boundary(self):
        source = inspect.getsource(
            identity
        )

        self.assertIn(
            "http://169.254.169.254/computeMetadata/v1",
            source,
        )
        self.assertIn(
            "ProxyHandler({})",
            source,
        )
        self.assertIn(
            "metadata redirect forbidden",
            source,
        )
        self.assertIn(
            '"Metadata-Flavor": "Google"',
            source,
        )
        self.assertNotIn(
            "os.getenv",
            source,
        )
        self.assertNotIn(
            "requests.",
            source,
        )

    def test_metadata_value_reader_enforces_url_header_and_size(self):
        approved_path = "/instance/name"
        approved_url = (
            identity.METADATA_BASE_URL
            + approved_path
        )

        class FakeResponse:
            def __init__(
                self,
                value=b"aurora-trading-vps",
                url=approved_url,
                flavor="Google",
            ):
                self.value = value
                self.url = url
                self.headers = {
                    "Metadata-Flavor":
                    flavor
                }

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return self.url

            def read(self, size):
                return self.value[:size]

        class FakeOpener:
            def __init__(self, response):
                self.response = response
                self.requests = []

            def open(self, request, timeout):
                self.requests.append(
                    (request, timeout)
                )
                return self.response

        opener = FakeOpener(
            FakeResponse()
        )
        value = identity._read_metadata_value(
            opener,
            approved_path,
        )
        self.assertEqual(
            value,
            "aurora-trading-vps",
        )
        self.assertEqual(
            opener.requests[0][1],
            1.0,
        )

        with self.assertRaises(
            ValueError
        ):
            identity._read_metadata_value(
                FakeOpener(
                    FakeResponse(
                        url="http://example.invalid/",
                    )
                ),
                approved_path,
            )

        with self.assertRaises(
            ValueError
        ):
            identity._read_metadata_value(
                FakeOpener(
                    FakeResponse(
                        flavor="NotGoogle",
                    )
                ),
                approved_path,
            )

        with self.assertRaises(
            ValueError
        ):
            identity._read_metadata_value(
                FakeOpener(
                    FakeResponse(
                        value=b"x" * 1025,
                    )
                ),
                approved_path,
            )

    def test_unapproved_metadata_path_is_rejected_before_network(self):
        class NeverUsed:
            def open(self, *args, **kwargs):
                raise AssertionError(
                    "network must not be used"
                )

        with self.assertRaises(
            ValueError
        ):
            identity._read_metadata_value(
                NeverUsed(),
                "/instance/service-accounts/default/token",
            )


if __name__ == "__main__":
    unittest.main()
