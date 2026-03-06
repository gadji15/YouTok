from __future__ import annotations

import argparse
from pathlib import Path

import structlog

from video_worker.pipeline.text_aware_crop import TextAwareCropConfig, render_text_aware_crop
from video_worker.utils.ffprobe import probe_video

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


def _load_yaml(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("pyyaml_not_installed")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SystemExit("config_must_be_a_mapping")
    return dict(raw)


def main() -> int:
    ap = argparse.ArgumentParser(description="Text-aware dynamic vertical crop (CPU MVP)")
    ap.add_argument("--config", help="Optional YAML config (see text_aware_crop_config.example.yaml)")

    ap.add_argument("--input", required=True, help="Input video path")
    ap.add_argument("--output", required=True, help="Output mp4 path")
    ap.add_argument("--start", type=float, default=None, help="Start seconds")
    ap.add_argument("--end", type=float, default=None, help="End seconds (default: full duration)")

    ap.add_argument("--out_w", type=int, default=None)
    ap.add_argument("--out_h", type=int, default=None)
    ap.add_argument("--sample_fps", type=float, default=None)
    ap.add_argument("--padding_ratio", type=float, default=None)
    ap.add_argument("--ocr_lang", type=str, default=None)
    ap.add_argument("--ocr_conf_threshold", type=float, default=None)
    ap.add_argument("--min_zoom", type=float, default=None)
    ap.add_argument("--max_zoom", type=float, default=None)
    ap.add_argument("--reading_hold_sec", type=float, default=None)
    ap.add_argument("--target_fps", type=int, default=None)

    ap.add_argument("--debug_frames", action=argparse.BooleanOptionalAction, default=None)

    args = ap.parse_args()

    source = Path(args.input).expanduser().resolve()
    out = Path(args.output).expanduser().resolve()

    if not source.exists():
        raise SystemExit(f"input_not_found: {source}")

    cfg_file: dict = {}
    if args.config:
        cfg_file = _load_yaml(Path(args.config).expanduser().resolve())

    def _val(name: str, default):
        v = getattr(args, name)
        if v is not None:
            return v
        if name in cfg_file:
            return cfg_file[name]
        return default

    if args.end is None:
        info = probe_video(source)
        end = float(_val("end", float(info.duration_seconds)))
    else:
        end = float(args.end)

    cfg = TextAwareCropConfig(
        out_w=int(_val("out_w", 1080)),
        out_h=int(_val("out_h", 1920)),
        sample_fps=float(_val("sample_fps", 5.0)),
        padding_ratio=float(_val("padding_ratio", 0.18)),
        ocr_lang=str(_val("ocr_lang", "eng+fra+ara")),
        ocr_conf_threshold=float(_val("ocr_conf_threshold", 60.0)),
        min_zoom=float(_val("min_zoom", 1.0)),
        max_zoom=float(_val("max_zoom", 1.9)),
        reading_hold_sec=float(_val("reading_hold_sec", 0.8)),
        debug_frames=bool(_val("debug_frames", False)),
    )

    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    logger = structlog.get_logger().bind(tool="text_aware_crop")

    output_dir = out.parent / (out.stem + "_artifacts")

    render_text_aware_crop(
        source_video=source,
        start_seconds=float(_val("start", 0.0)),
        end_seconds=float(end),
        output_video=out,
        output_dir=output_dir,
        cfg=cfg,
        logger=logger,
        target_fps=int(_val("target_fps", 30)),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
