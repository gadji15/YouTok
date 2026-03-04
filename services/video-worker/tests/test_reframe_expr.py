from __future__ import annotations

from video_worker.pipeline.clip import _build_piecewise_linear_x_expr


def test_build_piecewise_linear_x_expr_returns_string() -> None:
    expr = _build_piecewise_linear_x_expr(t_points=[0.0, 5.0, 10.0], x_points=[0, 100, 50])

    # Should reference t, include between() guards, and be deterministic.
    assert "between(t" in expr
    assert "t-0.0" in expr or "t-0" in expr
    # The final fallback should be the last x value.
    assert expr.endswith(",50))") or expr.endswith(",50)")


def test_build_piecewise_linear_single_point() -> None:
    expr = _build_piecewise_linear_x_expr(t_points=[0.0], x_points=[123])
    assert expr == "123"
