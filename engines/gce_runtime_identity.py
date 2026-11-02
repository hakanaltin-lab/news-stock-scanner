"""Read and validate fixed GCE runtime identity from the link-local metadata service.

The metadata endpoint is fixed to 169.254.169.254, proxy use is disabled, redirects
are rejected, and only non-secret instance identity attributes are read.
"""

from __future__ import annotations

from http.client import HTTPResponse
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)
import re


ENGINE_VERSION = "AURORA G7.7 GCE Runtime Identity"
METADATA_BASE_URL = (
    "http://169.254.169.254/computeMetadata/v1"
)
EXPECTED_PROJECT_ID = "project-ce9773ef-6814-469c-92b"
EXPECTED_INSTANCE_NAME = "aurora-trading-vps"
EXPECTED_ZONE = "europe-west3-a"
MAX_METADATA_VALUE_BYTES = 1024

_METADATA_PATHS = {
    "project_id": "/project/project-id",
    "instance_name": "/instance/name",
    "zone_path": "/instance/zone",
    "instance_id": "/instance/id",
}

_INSTANCE_ID = re.compile(r"^[1-9][0-9]{5,30}$")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        raise HTTPError(
            req.full_url,
            code,
            "metadata redirect forbidden",
            headers,
            fp,
        )


def evaluate_gce_runtime_identity(
    project_id,
    instance_name,
    zone_path,
    instance_id,
):
    failures = []

    def require(name, condition):
        if not condition:
            failures.append(name)

    project_id = str(
        project_id or ""
    ).strip()
    instance_name = str(
        instance_name or ""
    ).strip()
    zone_path = str(
        zone_path or ""
    ).strip()
    instance_id = str(
        instance_id or ""
    ).strip()

    zone = (
        zone_path.rsplit(
            "/",
            1,
        )[-1]
        if zone_path
        else ""
    )

    require(
        "project_id_matches_approved_project",
        project_id == EXPECTED_PROJECT_ID,
    )
    require(
        "instance_name_matches_approved_vps",
        instance_name == EXPECTED_INSTANCE_NAME,
    )
    require(
        "zone_path_valid",
        zone_path.endswith(
            "/zones/"
            + EXPECTED_ZONE
        ),
    )
    require(
        "zone_matches_approved_zone",
        zone == EXPECTED_ZONE,
    )
    require(
        "instance_id_valid",
        bool(
            _INSTANCE_ID.fullmatch(
                instance_id
            )
        ),
    )

    verified = not failures

    return {
        "engine": ENGINE_VERSION,
        "status": (
            "VERIFIED"
            if verified
            else "BLOCKED"
        ),
        "verified": verified,
        "project_id": (
            project_id
            if verified
            else None
        ),
        "instance_name": (
            instance_name
            if verified
            else None
        ),
        "zone": (
            zone
            if verified
            else None
        ),
        "instance_id": (
            instance_id
            if verified
            else None
        ),
        "failure_reasons": failures,
    }


def _read_metadata_value(
    opener,
    path,
):
    if path not in _METADATA_PATHS.values():
        raise ValueError(
            "unapproved metadata path"
        )

    url = (
        METADATA_BASE_URL
        + path
    )

    request = Request(
        url,
        headers={
            "Metadata-Flavor": "Google",
        },
        method="GET",
    )

    response = opener.open(
        request,
        timeout=1.0,
    )

    with response:
        if response.geturl() != url:
            raise ValueError(
                "metadata redirect detected"
            )

        if (
            response.headers.get(
                "Metadata-Flavor"
            )
            !=
            "Google"
        ):
            raise ValueError(
                "metadata flavor response missing"
            )

        raw = response.read(
            MAX_METADATA_VALUE_BYTES
            + 1
        )

    if (
        not raw
        or len(raw)
        >
        MAX_METADATA_VALUE_BYTES
    ):
        raise ValueError(
            "metadata value size invalid"
        )

    return raw.decode(
        "utf-8",
        errors="strict",
    ).strip()


def read_gce_runtime_identity():
    """Read the approved VM identity. Any metadata error is fail-closed."""

    opener = build_opener(
        ProxyHandler({}),
        _NoRedirect(),
    )

    values = {}

    try:
        for name, path in _METADATA_PATHS.items():
            values[name] = (
                _read_metadata_value(
                    opener,
                    path,
                )
            )
    except (
        HTTPError,
        URLError,
        OSError,
        UnicodeDecodeError,
        ValueError,
    ) as error:
        return {
            "engine": ENGINE_VERSION,
            "status": "BLOCKED",
            "verified": False,
            "project_id": None,
            "instance_name": None,
            "zone": None,
            "instance_id": None,
            "failure_reasons": [
                "GCE_METADATA_IDENTITY_UNAVAILABLE"
            ],
            "error_class": type(error).__name__,
        }

    return evaluate_gce_runtime_identity(
        project_id=values.get(
            "project_id"
        ),
        instance_name=values.get(
            "instance_name"
        ),
        zone_path=values.get(
            "zone_path"
        ),
        instance_id=values.get(
            "instance_id"
        ),
    )
