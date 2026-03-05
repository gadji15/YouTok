from __future__ import annotations

from video_worker.pipeline.transcript_cleanup import spellcheck_cleanup_text


def test_spellcheck_cleanup_text_corrects_basic_typo_en(monkeypatch) -> None:
    class FakeSpellChecker:
        def __init__(self, language: str):
            self.language = language

        def unknown(self, words):
            return {w for w in words if w == "teh"}

        def correction(self, word: str):
            return "the" if word == "teh" else word

    monkeypatch.setattr("video_worker.pipeline.transcript_cleanup._SpellChecker", FakeSpellChecker)

    out = spellcheck_cleanup_text("teh truth", language="en")
    assert out == "the truth"


def test_spellcheck_cleanup_text_is_conservative_for_capitalized_tokens(monkeypatch) -> None:
    class FakeSpellChecker:
        def __init__(self, language: str):
            self.language = language

        def unknown(self, words):
            return {"teh"}

        def correction(self, word: str):
            return "the"

    monkeypatch.setattr("video_worker.pipeline.transcript_cleanup._SpellChecker", FakeSpellChecker)

    out = spellcheck_cleanup_text("Teh truth", language="en")
    # We only correct fully lowercase tokens.
    assert out == "Teh truth"
