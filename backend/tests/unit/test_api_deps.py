import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.api.deps import get_current_user_id
from src.config import Config, set_config_override


def _build_request(headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (key.lower().encode("utf-8"), value.encode("utf-8"))
                for key, value in headers.items()
            ],
        }
    )


@pytest.fixture()
def unsigned_config():
    config = Config()
    config.backend_auth_secret = None
    config.require_signed_auth = False
    set_config_override(config)
    yield config
    set_config_override(None)


def test_accepts_plain_user_id_header(unsigned_config):
    request = _build_request({"user_id": "user-42"})
    assert get_current_user_id(request) == "user-42"


def test_accepts_supoclip_user_id_header(unsigned_config):
    request = _build_request({"x-supoclip-user-id": "user-7"})
    assert get_current_user_id(request) == "user-7"


def test_rejects_missing_user_id(unsigned_config):
    with pytest.raises(HTTPException) as exc:
        get_current_user_id(_build_request({}))
    assert exc.value.status_code == 401


def test_signed_mode_rejects_unsigned_headers():
    config = Config()
    config.backend_auth_secret = "secret"
    config.require_signed_auth = True
    set_config_override(config)
    try:
        with pytest.raises(HTTPException) as exc:
            get_current_user_id(_build_request({"user_id": "user-1"}))
        assert exc.value.status_code == 401
    finally:
        set_config_override(None)
