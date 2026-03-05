from __future__ import annotations

import re
import time
from pathlib import Path

import httpx
import structlog

from .transcribe import transcribe_audio
from .types import ClipCandidate, TranscriptSegment, WordTiming
from .word_alignment import approximate_words_from_segments


VOICEOVER_SCRIPT_PROMPT = """You are a short-form narrator.

Task:
- Rewrite the transcript excerpt into a concise voice-over script.
- The result must sound original and editorialized: paraphrase, summarize, add context.
- Keep the language consistent with the requested language.

Rules:
- Output ONLY the final script text.
- No markdown, no quotes, no JSON.
- Do not include timestamps.
- Avoid long verbatim quotes from the transcript.
"""


_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


def _extract_window_text(*, clip: ClipCandidate, segments: list[TranscriptSegment]) -> str:
    parts: list[str] = []
    for s in segments:
        if s.end_seconds <= clip.start_seconds:
            continue
        if s.start_seconds >= clip.end_seconds:
            break
        txt = s.text.strip()
        if txt:
            parts.append(txt)
    return " ".join(parts).strip()


def _truncate_to_max_words(text: str, max_words: int) -> str:
    words = _WORD_RE.findall(text)
    if max_words <= 0 or len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip()


def generate_voiceover_script(
    *,
    transcript_text: str,
    language: str | None,
    target_seconds: float,
    openai_api_key: str,
    openai_model: str,
    openai_base_url: str,
    logger: structlog.BoundLogger,
    timeout_seconds: float = 35.0,
) -> str:
    # Short-form narration typically sits around 2.0–2.5 words/sec.
    max_words = int(max(40.0, float(target_seconds) * 2.2))

    url = openai_base_url.rstrip("/") + "/chat/completions"

    user = (
        f"Language: {(language or 'en').lower().strip()}\n"
        f"Target duration: {round(float(target_seconds), 2)}s\n"
        f"Max words: {max_words}\n\n"
        f"Transcript excerpt (verbatim):\n{transcript_text}"
    )

    started = time.time()
    res = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": openai_model,
            "temperature": 0.6,
            "messages": [
                {"role": "system", "content": VOICEOVER_SCRIPT_PROMPT},
                {"role": "user", "content": user},
            ],
        },
        timeout=timeout_seconds,
    )

    res.raise_for_status()
    data = res.json()

    content = (
        (((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
        if isinstance(data, dict)
        else None
    )

    if not content or not isinstance(content, str):
        raise RuntimeError("openai: missing voiceover script")

    script = re.sub(r"\s+", " ", content.strip())
    script = _truncate_to_max_words(script, max_words=max_words)

    logger.info(
        "voiceover.script_generated",
        duration_ms=int((time.time() - started) * 1000),
        model=openai_model,
        max_words=max_words,
        out_words=len(_WORD_RE.findall(script)),
    )

    return script


def openai_tts_to_wav(
    *,
    text: str,
    output_path: Path,
    api_key: str,
    base_url: str,
    model: str,
    voice: str,
    instructions: str,
    logger: structlog.BoundLogger,
    timeout_seconds: float = 60.0,
) -> None:
    url = base_url.rstrip("/") + "/audio/speech"

    started = time.time()
    res = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "voice": voice,
            "input": text,
            "instructions": instructions,
            "response_format": "wav",
        },
        timeout=timeout_seconds,
    )
    res.raise_for_status()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(res.content)

    logger.info(
        "voiceover.tts_generated",
        duration_ms=int((time.time() - started) * 1000),
        tts_model=model,
        voice=voice,
        bytes=len(res.content),
    )


def build_voiceover_overrides(
    *,
    clips: list[ClipCandidate],
    transcript_segments: list[TranscriptSegment],
    language: str | None,
    openai_api_key: str,
    openai_model: str,
    openai_base_url: str,
    tts_model: str,
    tts_voice: str,
    tts_instructions: str,
    whisper_model: str,
    whisper_device: str,
    whisper_temperature: float,
    whisper_beam_size: int,
    whisper_best_of: int,
    whisper_initial_prompt: str | None,
    clips_dir: Path,
    logger: structlog.BoundLogger,
) -> tuple[list[TranscriptSegment], dict[str, list[WordTiming]], dict[str, Path]]:
    segments_out: list[TranscriptSegment] = []
    words_by_clip_id: dict[str, list[WordTiming]] = {}
    audio_by_clip_id: dict[str, Path] = {}

    for clip in clips:
        clip_dir = clips_dir / clip.clip_id
        clip_dir.mkdir(parents=True, exist_ok=True)

        duration = max(0.01, float(clip.end_seconds - clip.start_seconds))
        excerpt = _extract_window_text(clip=clip, segments=transcript_segments)

        script = generate_voiceover_script(
            transcript_text=excerpt,
            language=language,
            target_seconds=duration,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            openai_base_url=openai_base_url,
            logger=logger.bind(clip_id=clip.clip_id),
        )

        (clip_dir / "voiceover.txt").write_text(script + "\n", encoding="utf-8")

        wav_path = clip_dir / "voiceover.wav"
        openai_tts_to_wav(
            text=script,
            output_path=wav_path,
            api_key=openai_api_key,
            base_url=openai_base_url,
            model=tts_model,
            voice=tts_voice,
            instructions=tts_instructions,
            logger=logger.bind(clip_id=clip.clip_id),
        )

        rel_segments = transcribe_audio(
            audio_path=wav_path,
            model_name=whisper_model,
            logger=logger.bind(clip_id=clip.clip_id),
            language=language,
            initial_prompt=whisper_initial_prompt,
            device=whisper_device,
            temperature=whisper_temperature,
            beam_size=whisper_beam_size,
            best_of=whisper_best_of,
        )

        offset = float(clip.start_seconds)
        abs_segments = [
            TranscriptSegment(
                start_seconds=float(s.start_seconds) + offset,
                end_seconds=float(s.end_seconds) + offset,
                text=s.text,
            )
            for s in rel_segments
        ]

        segments_out.extend(abs_segments)

        approx_words = approximate_words_from_segments(segments=rel_segments)
        words_by_clip_id[clip.clip_id] = [
            WordTiming(
                word=w.word,
                start_seconds=float(w.start_seconds) + offset,
                end_seconds=float(w.end_seconds) + offset,
                confidence=w.confidence,
            )
            for w in approx_words
        ]

        audio_by_clip_id[clip.clip_id] = wav_path

    segments_out.sort(key=lambda s: (s.start_seconds, s.end_seconds))
    return segments_out, words_by_clip_id, audio_by_clip_id
