"""Scheduled auto-cleanup rules, e.g. "every week recycle phone thumbnail cache for all users".

Rules only ever move files to the recycle bin (restorable for TRASH_RETENTION_DAYS)."""
import json
import logging
import secrets
import time

from . import db, fileops, jobs, queries, scope, features

log = logging.getLogger("supergallery")
EVERY = {"daily": 86400, "weekly": 7 * 86400, "monthly": 30 * 86400}

# Ready-made rules the UI offers as one-tap templates.
TEMPLATES = [
    {"name": "Phone thumbnail cache", "target": {"kind": "cache"}, "older_days": 0, "every": "weekly"},
    {"name": "Phone recycle-bin leftovers older than 30 days", "target": {"kind": "phonetrash"}, "older_days": 30,
     "every": "weekly"},
    {"name": "System junk files", "target": {"smart": "junk"}, "older_days": 0, "every": "weekly"},
    {"name": "Unfinished downloads older than 14 days", "target": {"smart": "temp"}, "older_days": 14,
     "every": "weekly"},
    {"name": "Screenshots older than 1 year", "target": {"kind": "screenshot"}, "older_days": 365,
     "every": "monthly"},
]


def load() -> list[dict]:
    try:
        return json.loads(db.kv_get("rules", "[]"))
    except ValueError:
        return []


def save(rules: list[dict]):
    clean = []
    for r in rules:
        t = r.get("target") or {}
        if not any(k in t for k in ("kind", "smart", "ext")):
            continue
        clean.append({
            "id": r.get("id") or secrets.token_hex(4), "name": str(r.get("name") or "Rule")[:80],
            "enabled": bool(r.get("enabled", True)), "target": {k: t[k] for k in ("kind", "smart", "ext") if k in t},
            "older_days": max(0, int(r.get("older_days") or 0)), "every": r.get("every") if r.get("every") in EVERY else "weekly",
            "users": [u for u in (r.get("users") or []) if isinstance(u, str)] or None,
            "last_run": r.get("last_run") or time.time(), "last_result": r.get("last_result"),
        })
    db.kv_set("rules", json.dumps(clean))
    return clean


def _filter(rule: dict) -> dict:
    f = dict(rule["target"])
    if rule.get("older_days"):
        f["mtime_before"] = time.time() - rule["older_days"] * 86400
    return f


def preview(rule: dict) -> dict:
    prev = scope.owners()
    try:
        scope.set_owners(rule.get("users"))
        where, p = queries.build_where(_filter(rule))
        n, s = db.conn().execute(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM files{where}", p).fetchone()
        return {"count": n, "size": s}
    finally:
        scope.set_owners(list(prev) if prev else None)


def run(task, rule_id: str):
    if not features.enabled('automation'):
        raise jobs.Cancelled()
    rules = load()
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if not rule:
        return {"error": "rule not found"}
    scope.set_owners(rule.get("users"))
    try:
        ids = queries.ids_for(_filter(rule))
    finally:
        scope.set_owners(None)
    res = fileops.delete(task, ids=ids, permanent=False, guard="dupes", reason=f"rule: {rule['name']}") if ids \
        else {"deleted": 0, "freed": 0}
    rule["last_run"] = time.time()
    rule["last_result"] = {"deleted": res.get("deleted", 0), "freed": res.get("freed", 0)}
    save(rules)
    queries.invalidate()
    log.info("rule '%s' ran: %s", rule["name"], rule["last_result"])
    return res


def due():
    """Called by the scheduler: queue every enabled rule whose interval has passed."""
    if not features.enabled('automation'):
        return
    now = time.time()
    for r in load():
        if r["enabled"] and now - (r.get("last_run") or 0) >= EVERY[r["every"]]:
            jobs.ops.submit(jobs.Task("rule", f"Auto-cleanup: {r['name']}", run, r["id"]))
