import pytest

from app import db, features, updates


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "index.db")
    db._local.__dict__.clear()
    db.init()
    monkeypatch.delenv("UPDATE_CHECK", raising=False)
    return monkeypatch


def release(tag):
    return lambda: {"latest": tag.lstrip("v"), "name": "SuperGallery " + tag, "notes": "## Notes\n- one", "url": "u", "published": "p"}


def test_newer_release_is_offered(store):
    store.setattr(updates, "_fetch", release("v9.0.0"))
    s = updates.status(force=True)
    assert s["available"] and s["latest"] == "9.0.0" and s["current"] == features.VERSION


def test_same_or_older_release_is_not_offered(store):
    store.setattr(updates, "_fetch", release("v" + features.VERSION))
    assert not updates.status(force=True)["available"]
    store.setattr(updates, "_fetch", release("v0.1.0"))
    assert not updates.status(force=True)["available"]


def test_checks_can_be_turned_off(store):
    calls = []
    store.setattr(updates, "_fetch", lambda: calls.append(1) or release("v9.0.0")())
    updates.set_enabled({"enabled": False})
    assert not updates.status(force=True)["available"] and not calls
    store.setenv("UPDATE_CHECK", "0")
    updates.set_enabled({"enabled": True})
    assert not updates.status(force=True)["enabled"] and not calls


def test_offline_check_keeps_last_answer_and_explains(store):
    store.setattr(updates, "_fetch", release("v9.0.0"))
    updates.status(force=True)

    def offline():
        raise OSError("no network")
    store.setattr(updates, "_fetch", offline)
    s = updates.status(force=True)
    assert s["available"] and s["latest"] == "9.0.0" and "GitHub" in s["error"]


def test_one_click_needs_watchtower(store):
    store.setattr(updates, "WATCHTOWER_URL", "")
    with pytest.raises(Exception) as err:
        updates.apply()
    assert "Watchtower" in str(err.value.detail)
