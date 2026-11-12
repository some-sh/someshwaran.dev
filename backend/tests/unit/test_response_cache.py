"""ETags, conditional-request matching and the render cache."""

from datetime import UTC, datetime, timedelta

from app.services import response_cache
from app.services.response_cache import RenderCache, etag_for, matches
from app.services.resume_service import ResumeStamp

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _stamp(resume_id: int = 1, updated_at: datetime = _NOW) -> ResumeStamp:
    return ResumeStamp(id=resume_id, name="r", updated_at=updated_at)


def test_etag_is_a_stable_quoted_strong_validator():
    etag = etag_for("json", _stamp())

    assert etag == etag_for("json", _stamp())
    assert etag.startswith('"') and etag.endswith('"') and not etag.startswith('W/"')


def test_etag_changes_with_every_input_that_changes_the_bytes():
    base = etag_for("pdf", _stamp(), "ats")

    assert etag_for("pdf", _stamp(2), "ats") != base  # another resume
    assert etag_for("pdf", _stamp(updated_at=_NOW + timedelta(seconds=1)), "ats") != base  # edited
    assert etag_for("docx", _stamp(), "ats") != base  # another format
    assert etag_for("pdf", _stamp(), "other") != base  # another template


def test_etag_changes_when_the_rendering_code_changes(monkeypatch):
    before = etag_for("pdf", _stamp(), "ats")

    monkeypatch.setattr(response_cache, "RENDER_FINGERPRINT", "a-new-template-version")

    assert (
        etag_for("pdf", _stamp(), "ats") != before
    )  # a deploy must not leave clients on old output


def test_matches_follows_if_none_match_rules():
    etag = '"abc"'

    assert matches('"abc"', etag)
    assert matches('"zzz", "abc"', etag)  # a list
    assert matches('W/"abc"', etag)  # weak validators compare equal for GET
    assert matches("*", etag)
    assert not matches('"other"', etag)
    assert not matches("", etag)
    assert not matches(None, etag)


def test_render_cache_renders_once_per_key():
    cache = RenderCache()
    calls: list[str] = []

    def render(label: str):
        def _render() -> bytes:
            calls.append(label)
            return label.encode()

        return _render

    assert cache.get_or_render("k1", render("one")) == b"one"
    assert cache.get_or_render("k1", render("again")) == b"one"  # served from cache
    assert cache.get_or_render("k2", render("two")) == b"two"
    assert calls == ["one", "two"]


def test_render_cache_is_bounded_and_evicts_the_least_recently_used():
    cache = RenderCache(max_entries=2)
    cache.get_or_render("a", lambda: b"a")
    cache.get_or_render("b", lambda: b"b")
    cache.get_or_render("a", lambda: b"unused")  # touch a: b is now the oldest
    cache.get_or_render("c", lambda: b"c")  # evicts b

    renders: list[str] = []
    cache.get_or_render("a", lambda: renders.append("a") or b"a")
    cache.get_or_render("b", lambda: renders.append("b") or b"b")

    assert renders == ["b"]  # a survived, b had been evicted
