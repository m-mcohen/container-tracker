"""Unit tests for container_tracker.core.updates (GitHub Releases polling)."""

from container_tracker.core import updates


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def _patch_get(monkeypatch, resp=None, exc=None):
    def fake_get(url, timeout):
        if exc is not None:
            raise exc
        return resp
    monkeypatch.setattr(updates.requests, "get", fake_get)


class TestCheckForUpdate:
    def test_newer_release_is_available(self, monkeypatch):
        monkeypatch.setattr(updates, "__version__", "1.0.0")
        _patch_get(monkeypatch, _Resp(200, {
            "tag_name": "v9.9.9",
            "html_url": "https://github.com/m-mcohen/container-tracker/releases/tag/v9.9.9",
        }))

        r = updates.check_for_update()

        assert r["available"] is True
        assert r["tag"] == "9.9.9"  # leading v stripped
        assert r["url"].endswith("/v9.9.9")

    def test_same_version_not_available(self, monkeypatch):
        monkeypatch.setattr(updates, "__version__", "2.0.0")
        _patch_get(monkeypatch, _Resp(200, {"tag_name": "v2.0.0", "html_url": "u"}))

        assert updates.check_for_update() == {
            "available": False, "tag": "", "url": "",
        }

    def test_older_release_not_available(self, monkeypatch):
        monkeypatch.setattr(updates, "__version__", "2.0.0")
        _patch_get(monkeypatch, _Resp(200, {"tag_name": "v1.9.0", "html_url": "u"}))

        assert updates.check_for_update()["available"] is False

    def test_http_error_reports_no_update(self, monkeypatch):
        # Private repo / rate limit → 404/403; must never raise.
        _patch_get(monkeypatch, _Resp(404, {"message": "Not Found"}))

        assert updates.check_for_update()["available"] is False

    def test_network_exception_reports_no_update(self, monkeypatch):
        _patch_get(monkeypatch, exc=ConnectionError("offline"))

        assert updates.check_for_update()["available"] is False

    def test_missing_tag_reports_no_update(self, monkeypatch):
        _patch_get(monkeypatch, _Resp(200, {"html_url": "u"}))

        assert updates.check_for_update()["available"] is False


class TestCheckForUpdateAsync:
    def test_callback_fires_for_newer_release(self, monkeypatch):
        import threading

        monkeypatch.setattr(updates, "__version__", "1.0.0")
        _patch_get(monkeypatch, _Resp(200, {"tag_name": "v9.9.9", "html_url": "u"}))
        got = {}
        done = threading.Event()

        def on_update(tag, url):
            got["tag"], got["url"] = tag, url
            done.set()

        updates.check_for_update_async(on_update)

        assert done.wait(timeout=5), "callback never fired"
        assert got == {"tag": "9.9.9", "url": "u"}
