"""Golden-vector tests: the engine must match fixtures/golden_vectors.json
exactly. The Swift port in the staccato-apple repo runs the same vectors —
this is the bit-for-bit cross-repo parity contract."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from asl_backend.engine import ENGINE_VERSION
from asl_backend.engine.scoring import (
    build_heatmap,
    label_for_score,
    pacing_score,
    summarize_cuts,
)

FIXTURES = json.loads(
    (Path(__file__).parent.parent.parent / "fixtures" / "golden_vectors.json").read_text()
)

TOL = 1e-9


def test_engine_version_matches_fixture():
    assert FIXTURES["engine_version"] == ENGINE_VERSION


@pytest.mark.parametrize("vector", FIXTURES["pacing_score"], ids=lambda v: f"m={v['median_shot_s']}")
def test_pacing_score_vectors(vector):
    score = pacing_score(vector["median_shot_s"])
    assert math.isclose(score, vector["score"], abs_tol=TOL)
    assert label_for_score(score) == vector["label"]


@pytest.mark.parametrize("vector", FIXTURES["heatmap"], ids=lambda v: v["name"])
def test_heatmap_vectors(vector):
    centers, densities = build_heatmap(
        vector["cut_times"], vector["duration_s"], vector["bin_s"], vector["window_s"]
    )
    assert len(centers) == len(vector["bin_centers_s"])
    for got, want in zip(centers, vector["bin_centers_s"]):
        assert math.isclose(got, want, abs_tol=TOL)
    for got, want in zip(densities, vector["cuts_per_min"]):
        assert math.isclose(got, want, abs_tol=TOL)


@pytest.mark.parametrize("vector", FIXTURES["summarize"], ids=lambda v: v["name"])
def test_summarize_vectors(vector):
    summary = summarize_cuts(vector["cut_times"], vector["duration_s"]).as_dict()
    expected = vector["expected"]
    for key in ("engine_version", "label", "cut_count"):
        assert summary[key] == expected[key]
    for key in ("duration_s", "median_shot_s", "cuts_per_minute", "score"):
        assert math.isclose(summary[key], expected[key], abs_tol=TOL)
    for got, want in zip(summary["heatmap"]["cuts_per_min"], expected["heatmap"]["cuts_per_min"]):
        assert math.isclose(got, want, abs_tol=TOL)


def test_score_anchors():
    """The published anchor points from the verified reference module."""
    assert round(pacing_score(2.0), 1) == 90.2
    assert round(pacing_score(15.0), 1) == 40.1
    assert pacing_score(11.0) == 50.0
    assert 18 < pacing_score(34.0) < 20
    assert 83 < pacing_score(3.0) < 85
    assert 92 < pacing_score(1.5) < 94


def test_labels():
    assert label_for_score(0) == "calm"
    assert label_for_score(24.999) == "calm"
    assert label_for_score(25) == "moderate"
    assert label_for_score(49.999) == "moderate"
    assert label_for_score(50) == "fast"
    assert label_for_score(74.999) == "fast"
    assert label_for_score(75) == "hyper-paced"
    assert label_for_score(100) == "hyper-paced"


def test_median_basis_resists_long_intro():
    """A long intro shouldn't drag a fast video's score down (median, not mean)."""
    # 60s intro then cuts every 2s for 60s
    cuts = [60.0 + 2.0 * i for i in range(1, 30)]
    summary = summarize_cuts(cuts, 120.0)
    assert summary.median_shot_s == 2.0
    assert summary.score > 85
