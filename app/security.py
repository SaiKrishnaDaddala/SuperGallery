"""Password + TOTP authentication. Secrets stay in /config; sessions are revocable.

SQLite transactions serialize OTP consumption, recovery-code use and enrollment.
This is a shared NAS app account, not the NAS user/owner picker.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

import pyotp
import qrcode
from cryptography.fernet import Fernet
from fastapi import HTTPException

SESSION_TTL = 12 * 3600
IDLE_TTL = 60 * 60
CHALLENGE_TTL = 300
ENROLL_TTL = 600
COOKIE = "sg_session"
CHALLENGE_COOKIE = "sg_challenge"


class Security:
    def __init__(self, directory, env_password="", clock=time.time):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.clock, self.env_password = clock, env_password
        self.password_file = self.directory / "password.json"
        self.database = self.directory / "security.sqlite3"
        keyfile = self.directory / "secret.key"
        try:
            with keyfile.open("x") as handle:
                handle.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        keyfile.chmod(0o600)
        self.key = keyfile.read_bytes().strip()
        if len(self.key) < 32:
            raise RuntimeError("Invalid security key; restore /config/secret.key from backup")
        self.cipher = Fernet(base64.urlsafe_b64encode(hmac.digest(self.key, b"totp-encryption-v1", "sha256")))
        with self.tx() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created REAL, expires REAL, seen REAL, password_tag TEXT, mfa INTEGER);
                CREATE TABLE IF NOT EXISTS challenges (id TEXT PRIMARY KEY, expires REAL, attempts INTEGER, password_tag TEXT);
                CREATE TABLE IF NOT EXISTS enrollment (session_id TEXT PRIMARY KEY, secret TEXT, expires REAL, attempts INTEGER);
                CREATE TABLE IF NOT EXISTS recovery (hash TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS limits (bucket TEXT PRIMARY KEY, count INTEGER, expires REAL);
            """)
        self.database.chmod(0o600)

    @contextmanager
    def tx(self):
        c = sqlite3.connect(self.database, timeout=15)
        c.row_factory = sqlite3.Row
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def digest(self, value):
        return hmac.new(self.key, value.encode(), hashlib.sha256).hexdigest()

    def password_record(self):
        try:
            return json.loads(self.password_file.read_text())
        except FileNotFoundError:
            return None
        # Corruption must fail closed, never reopen first-run setup.

    @staticmethod
    def password_hash(password, salt, rounds=600_000):
        return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), rounds).hex()

    def configured(self):
        return bool(self.env_password or self.password_record())

    def password_tag(self):
        record = self.password_record()
        marker = self.env_password or (record["hash"] if record else "")
        return self.digest("password:" + marker)

    def check_password(self, value):
        if not isinstance(value, str) or len(value) > 1024:
            return False
        if self.env_password:
            return hmac.compare_digest(value.encode(), self.env_password.encode())
        record = self.password_record()
        return bool(record) and hmac.compare_digest(self.password_hash(value, record["salt"], record.get("rounds", 200_000)), record["hash"])

    def write_password(self, value):
        if not isinstance(value, str) or not 12 <= len(value) <= 1024:
            raise HTTPException(400, "Use a password between 12 and 1024 characters.")
        salt = secrets.token_hex(16)
        record = {"salt": salt, "rounds": 600_000, "hash": self.password_hash(value, salt)}
        temp = self.password_file.with_suffix(".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(record, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.password_file)
        self.password_file.chmod(0o600)

    @staticmethod
    def get(c, key, default=None):
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    @staticmethod
    def put(c, key, value):
        c.execute("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def enabled(self):
        with self.tx() as c:
            return bool(self.get(c, "totp"))

    def throttle(self, operation, client):
        now = self.clock()
        limits = [(f"{operation}:ip:{self.digest(client)}", 10, 300), (f"{operation}:global", 60, 900)]
        blocked, retry = False, 1
        with self.tx() as c:
            c.execute("DELETE FROM limits WHERE expires<=?", (now,))
            for key, maximum, window in limits:
                bucket = key + ":" + str(int(now // window))
                expiry = (int(now // window) + 1) * window
                c.execute("INSERT INTO limits VALUES (?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1", (bucket, expiry))
                count = c.execute("SELECT count FROM limits WHERE bucket=?", (bucket,)).fetchone()[0]
                if count > maximum:
                    blocked, retry = True, max(retry, int(expiry - now) + 1)
        if blocked:
            raise HTTPException(429, "Too many attempts. Wait a few minutes and try again.", headers={"Retry-After": str(retry)})

    def _new_session(self, c, mfa):
        now, token = self.clock(), secrets.token_urlsafe(32)
        c.execute("DELETE FROM sessions WHERE expires<=? OR seen<=?", (now, now - IDLE_TTL))
        c.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)", (self.digest(token), now, now + SESSION_TTL, now, self.password_tag(), int(mfa)))
        return token

    def session(self, token, touch=True):
        if not token or len(token) > 256 or not self.configured():
            return None
        now, sid = self.clock(), self.digest(token)
        with self.tx() as c:
            row = c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
            if not row or row["expires"] <= now or row["seen"] <= now - IDLE_TTL or row["created"] > now or row["password_tag"] != self.password_tag() or (self.get(c, "totp") and not row["mfa"]):
                return None
            if touch and now - row["seen"] > 60:
                c.execute("UPDATE sessions SET seen=? WHERE id=?", (now, sid))
            return dict(row)

    def login(self, password, client):
        self.throttle("password", client)
        if not self.check_password(password):
            raise HTTPException(403, "The password is incorrect.")
        with self.tx() as c:
            if self.get(c, "totp"):
                token = secrets.token_urlsafe(32)
                c.execute("DELETE FROM challenges WHERE expires<=?", (self.clock(),))
                c.execute("INSERT INTO challenges VALUES (?,?,0,?)", (self.digest(token), self.clock() + CHALLENGE_TTL, self.password_tag()))
                return {"mfa_required": True, "challenge": token}
            return {"session": self._new_session(c, False)}

    def _verify_factor(self, c, code):
        code = str(code or "").strip()
        encrypted = self.get(c, "totp")
        if not encrypted:
            return False
        if re.fullmatch(r"[0-9]{6}", code):
            totp = pyotp.TOTP(self.cipher.decrypt(encrypted.encode()).decode())
            counter = int(self.clock() // 30)
            previous = int(self.get(c, "last_counter", -1))
            for step in (counter, counter - 1, counter + 1):
                if step > previous and hmac.compare_digest(totp.at(step * 30), code):
                    self.put(c, "last_counter", step)
                    return True
        else:
            normalized = re.sub(r"[\s-]", "", code).upper()
            if re.fullmatch(r"[A-Z2-7]{26}", normalized):
                changed = c.execute("DELETE FROM recovery WHERE hash=?", (self.digest("recovery:" + normalized),)).rowcount
                return changed == 1
        return False

    def verify_login(self, challenge, code, client):
        self.throttle("code", client)
        session = None
        with self.tx() as c:
            cid = self.digest(str(challenge or ""))
            row = c.execute("SELECT * FROM challenges WHERE id=?", (cid,)).fetchone()
            valid = row and row["expires"] > self.clock() and row["attempts"] < 5 and row["password_tag"] == self.password_tag()
            if valid:
                c.execute("UPDATE challenges SET attempts=attempts+1 WHERE id=?", (cid,))
                if self._verify_factor(c, code):
                    c.execute("DELETE FROM challenges WHERE id=?", (cid,))
                    session = self._new_session(c, True)
        if not session:
            raise HTTPException(403, "Code is invalid, expired, or already used. Try the next code, or sign in again after five attempts.")
        return session

    def reauthenticate(self, password, client):
        self.throttle("security", client)
        if not self.check_password(password):
            raise HTTPException(403, "The current password is incorrect.")

    def begin_enrollment(self, sid, password, client, account):
        self.reauthenticate(password, client)
        secret = pyotp.random_base32()
        with self.tx() as c:
            if self.get(c, "totp"):
                raise HTTPException(409, "An authenticator is already connected.")
            c.execute("DELETE FROM enrollment WHERE expires<=?", (self.clock(),))
            c.execute("INSERT OR REPLACE INTO enrollment VALUES (?,?,?,0)", (sid, self.cipher.encrypt(secret.encode()).decode(), self.clock() + ENROLL_TTL))
        uri = pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name="SuperGallery")
        stream = io.BytesIO()
        qrcode.make(uri, box_size=6, border=4).save(stream, format="PNG")
        return {"secret": secret, "qr": "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode(), "expires_in": ENROLL_TTL}

    def _recovery_codes(self, c):
        codes = [base64.b32encode(secrets.token_bytes(16)).decode().rstrip("=") for _ in range(10)]
        c.execute("DELETE FROM recovery")
        c.executemany("INSERT INTO recovery VALUES (?)", [(self.digest("recovery:" + code),) for code in codes])
        return ["-".join(code[i:i + 5] for i in range(0, len(code), 5)) for code in codes]

    @staticmethod
    def _revoke(c):
        c.execute("DELETE FROM sessions")
        c.execute("DELETE FROM challenges")
        c.execute("DELETE FROM enrollment")

    def confirm_enrollment(self, sid, code, client):
        self.throttle("code", client)
        result = None
        with self.tx() as c:
            row = c.execute("SELECT * FROM enrollment WHERE session_id=?", (sid,)).fetchone()
            if not self.get(c, "totp") and row and row["expires"] > self.clock() and row["attempts"] < 5:
                c.execute("UPDATE enrollment SET attempts=attempts+1 WHERE session_id=?", (sid,))
                totp = pyotp.TOTP(self.cipher.decrypt(row["secret"].encode()).decode())
                if re.fullmatch(r"[0-9]{6}", str(code or "")):
                    for step in (int(self.clock() // 30), int(self.clock() // 30) - 1, int(self.clock() // 30) + 1):
                        if hmac.compare_digest(totp.at(step * 30), code):
                            self.put(c, "totp", row["secret"])
                            self.put(c, "last_counter", step)
                            self._revoke(c)
                            result = {"session": self._new_session(c, True), "recovery_codes": self._recovery_codes(c)}
                            break
        if result is None:
            raise HTTPException(403, "That code did not match. Try again, or restart setup if it has expired.")
        return result

    def manage(self, action, sid, password, code, client):
        self.reauthenticate(password, client)
        result = None
        with self.tx() as c:
            enabled = bool(self.get(c, "totp"))
            if not enabled or self._verify_factor(c, code):
                if action == "disable":
                    c.execute("DELETE FROM settings WHERE key IN ('totp','last_counter')")
                    c.execute("DELETE FROM recovery")
                    enabled = False
                codes = self._recovery_codes(c) if action == "recovery" and enabled else None
                self._revoke(c)
                result = {"session": self._new_session(c, enabled)}
                if codes is not None:
                    result["recovery_codes"] = codes
        if result is None:
            raise HTTPException(403, "Authenticator or recovery code is invalid or already used.")
        return result

    def logout(self, token):
        with self.tx() as c:
            c.execute("DELETE FROM sessions WHERE id=?", (self.digest(token or ""),))

    def status(self):
        with self.tx() as c:
            return {"enabled": bool(self.get(c, "totp")), "recovery_remaining": c.execute("SELECT COUNT(*) FROM recovery").fetchone()[0],
                    "sessions": c.execute("SELECT COUNT(*) FROM sessions WHERE expires>? AND seen>?", (self.clock(), self.clock() - IDLE_TTL)).fetchone()[0],
                    "session_hours": SESSION_TTL // 3600, "idle_minutes": IDLE_TTL // 60}
