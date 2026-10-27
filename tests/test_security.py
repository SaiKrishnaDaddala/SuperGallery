import concurrent.futures
import hashlib
import json
import sqlite3

import pyotp
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.security import CHALLENGE_COOKIE, COOKIE, IDLE_TTL, Security

PASSWORD = "fixture-password-only-2026"


@pytest.fixture
def store(tmp_path):
    now = [1_800_000_000.0]
    security = Security(tmp_path, PASSWORD, clock=lambda: now[0])
    security.test_time = now
    return security


def enroll(store):
    token = store.login(PASSWORD, "test")["session"]
    sid = store.session(token)["id"]
    pending = store.begin_enrollment(sid, PASSWORD, "test", "fixture")
    code = pyotp.TOTP(pending["secret"]).at(store.clock())
    result = store.confirm_enrollment(sid, code, "test")
    return pending["secret"], result, token


def test_legacy_password_hash_remains_compatible(tmp_path):
    salt = "12" * 16
    record = {"salt": salt, "hash": hashlib.pbkdf2_hmac("sha256", PASSWORD.encode(), bytes.fromhex(salt), 200_000).hex()}
    (tmp_path / "password.json").write_text(json.dumps(record))
    store = Security(tmp_path)
    assert store.check_password(PASSWORD)
    assert not store.check_password("wrong")


def test_old_signed_cookie_is_rejected(store):
    assert store.session("1800000000." + "a" * 64) is None


def test_password_login_logout_and_expiry(store):
    token = store.login(PASSWORD, "one")["session"]
    assert store.session(token)
    store.logout(token)
    assert store.session(token) is None
    token = store.login(PASSWORD, "one")["session"]
    store.test_time[0] += IDLE_TTL + 1
    assert store.session(token) is None


def test_polling_does_not_extend_idle_session(store):
    token = store.login(PASSWORD, "one")["session"]
    store.test_time[0] += IDLE_TTL - 2
    assert store.session(token, touch=False)
    store.test_time[0] += 3
    assert store.session(token, touch=False) is None


def test_wrong_password_does_not_create_session(store):
    with pytest.raises(HTTPException) as error:
        store.login("wrong", "one")
    assert error.value.status_code == 403
    assert store.status()["sessions"] == 0


def test_enrollment_needs_password_and_matching_code(store):
    token = store.login(PASSWORD, "one")["session"]
    sid = store.session(token)["id"]
    with pytest.raises(HTTPException):
        store.begin_enrollment(sid, "wrong", "one", "fixture")
    setup = store.begin_enrollment(sid, PASSWORD, "one", "fixture")
    assert not store.enabled()
    assert setup["qr"].startswith("data:image/png;base64,")
    with pytest.raises(HTTPException):
        store.confirm_enrollment(sid, "abcdef", "one")
    assert not store.enabled()
    assert store.session(token)


def test_enabled_revokes_old_sessions_and_encrypts_secret(store):
    secret, result, previous = enroll(store)
    assert store.enabled()
    assert store.session(previous) is None
    assert store.session(result["session"])["mfa"] == 1
    assert secret.encode() not in store.database.read_bytes()
    assert len(result["recovery_codes"]) == 10
    for code in result["recovery_codes"]:
        assert code.replace("-", "").encode() not in store.database.read_bytes()


def test_password_only_challenge_is_not_a_session(store):
    enroll(store)
    challenge = store.login(PASSWORD, "one")
    assert challenge["mfa_required"]
    assert store.session(challenge["challenge"]) is None


def test_totp_replay_and_challenge_reuse_rejected(store):
    secret, _, _ = enroll(store)
    challenge = store.login(PASSWORD, "one")["challenge"]
    with pytest.raises(HTTPException):
        store.verify_login(challenge, pyotp.TOTP(secret).at(store.clock()), "one")
    store.test_time[0] += 30
    code = pyotp.TOTP(secret).at(store.clock())
    token = store.verify_login(challenge, code, "one")
    assert store.session(token)
    with pytest.raises(HTTPException):
        store.verify_login(challenge, code, "one")
    second = store.login(PASSWORD, "two")["challenge"]
    with pytest.raises(HTTPException):
        store.verify_login(second, code, "two")


def test_challenge_expires_and_has_five_attempt_limit(store):
    secret, _, _ = enroll(store)
    challenge = store.login(PASSWORD, "one")["challenge"]
    for _ in range(5):
        with pytest.raises(HTTPException):
            store.verify_login(challenge, "invalid", "one")
    store.test_time[0] += 30
    with pytest.raises(HTTPException):
        store.verify_login(challenge, pyotp.TOTP(secret).at(store.clock()), "one")
    challenge = store.login(PASSWORD, "two")["challenge"]
    store.test_time[0] += 301
    with pytest.raises(HTTPException):
        store.verify_login(challenge, pyotp.TOTP(secret).at(store.clock()), "two")


def test_recovery_code_can_only_be_consumed_once_concurrently(store):
    _, result, _ = enroll(store)
    challenges = [store.login(PASSWORD, str(i))["challenge"] for i in range(2)]
    def verify(pair):
        i, challenge = pair
        try:
            return store.verify_login(challenge, result["recovery_codes"][0], str(i))
        except HTTPException:
            return None
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        tokens = list(pool.map(verify, enumerate(challenges)))
    assert sum(bool(token) for token in tokens) == 1
    assert store.status()["recovery_remaining"] == 9


def test_disable_requires_password_and_second_factor(store):
    _, result, _ = enroll(store)
    sid = store.session(result["session"])["id"]
    with pytest.raises(HTTPException):
        store.manage("disable", sid, PASSWORD, "invalid", "one")
    assert store.enabled()
    disabled = store.manage("disable", sid, PASSWORD, result["recovery_codes"][0], "one")
    assert not store.enabled()
    assert store.session(result["session"]) is None
    assert store.session(disabled["session"])


def test_regeneration_invalidates_old_recovery_codes(store):
    _, result, _ = enroll(store)
    sid = store.session(result["session"])["id"]
    changed = store.manage("recovery", sid, PASSWORD, result["recovery_codes"][0], "one")
    assert len(changed["recovery_codes"]) == 10
    challenge = store.login(PASSWORD, "two")["challenge"]
    with pytest.raises(HTTPException):
        store.verify_login(challenge, result["recovery_codes"][1], "two")


def test_rate_limits_survive_restart(store):
    for _ in range(10):
        with pytest.raises(HTTPException):
            store.login("wrong", "one")
    restarted = Security(store.directory, PASSWORD, clock=store.clock)
    with pytest.raises(HTTPException) as error:
        restarted.login(PASSWORD, "one")
    assert error.value.status_code == 429


def test_corrupted_password_does_not_reopen_setup(tmp_path):
    (tmp_path / "password.json").write_text("broken")
    store = Security(tmp_path)
    with pytest.raises(json.JSONDecodeError):
        store.configured()


def test_http_boundary_and_secure_cookies(store, monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "http-config"))
    from app import auth_http
    monkeypatch.setattr(auth_http, "security", store)
    app = FastAPI()
    auth_http.install(app)
    @app.get("/api/protected")
    def protected():
        return {"private":True}
    with TestClient(app, base_url="https://nas.test", headers={"X-SG-Request":"1"}) as client:
        assert client.get("/api/protected").status_code == 401
        assert client.post("/api/login", json={"password":PASSWORD}, headers={"Origin":"https://attacker.test"}).status_code == 403
        login = client.post("/api/login", json={"password":PASSWORD})
        cookie = login.headers["set-cookie"].lower()
        assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
        assert client.get("/api/protected").status_code == 200
        client.post("/api/logout")
        assert client.get("/api/protected").status_code == 401
    _, result, _ = enroll(store)
    with TestClient(app, base_url="http://nas.test", headers={"X-SG-Request":"1"}) as client:
        assert client.get("/api/auth").json()["https_required"]
        client.cookies.set(COOKIE, result["session"])
        assert client.get("/api/protected").status_code == 426
        assert client.post("/api/login", json={"password":PASSWORD}).status_code == 426
