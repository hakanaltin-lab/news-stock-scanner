"""AURORA V8.9.5 fail-closed deployment environment manager.

LIVE is intentionally not a supported deployment environment.
"""

from datetime import datetime, timezone


VALID_ENVIRONMENTS = {"DEVELOPMENT", "PAPER"}


class EnvironmentManager:
    def __init__(self):
        self.status = "SAFE"
        self.environment = "DEVELOPMENT"
        self.version = "AURORA V8.9.5"
        self.configuration = {}

    def set_environment(self, environment):
        requested = str(environment or "").strip().upper()

        if requested not in VALID_ENVIRONMENTS:
            return {
                "status": "BLOCKED",
                "requested_environment": requested or None,
                "environment": self.environment,
                "reason": "UNSUPPORTED_OR_LIVE_ENVIRONMENT",
                "live_execution_allowed": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        self.environment = requested

        return {
            "status": "UPDATED",
            "environment": self.environment,
            "live_execution_allowed": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def add_configuration(self, key, value):
        self.configuration[key] = value
        return {key: value}

    def health_check(self):
        return {
            "system": "AURORA",
            "status": "HEALTHY",
            "environment": self.environment,
            "live_execution_allowed": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def generate_deployment_report(self):
        return {
            "engine": "V8.9.5 Fail-Closed Environment Manager",
            "version": self.version,
            "environment": self.environment,
            "configuration": self.configuration,
            "system_status": self.status,
            "live_execution_allowed": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
