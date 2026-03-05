from video_worker.pipeline.transcript_normalize import normalize_transcript_text


def test_normalize_transcript_text_canonicalizes_names():
    assert normalize_transcript_text("mouhamad") == "Muhammad"
    assert normalize_transcript_text("MOHAMED") == "Muhammad"
    assert normalize_transcript_text("ibrahim") == "Ibrahim"


def test_normalize_transcript_text_canonicalizes_common_phrases():
    # Common noisy transliteration drift
    txt = "salalahou haleyhi wa salam"
    out = normalize_transcript_text(txt)
    assert out == "sallallahu alayhi wa sallam"
