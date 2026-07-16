from __future__ import annotations

from asl_backend.models import Analysis, Video
from asl_backend.schemas import AnalysisOut, VideoOut


def _enum_value(v):
    return v.value if hasattr(v, "value") else v


def analysis_out(analysis: Analysis) -> AnalysisOut:
    return AnalysisOut(
        id=analysis.id,
        status=_enum_value(analysis.status),
        engine_version=analysis.engine_version,
        score=analysis.score,
        label=analysis.label,
        median_shot_s=analysis.median_shot_s,
        cuts_per_minute=analysis.cuts_per_minute,
        cut_count=analysis.cut_count,
        duration_s=analysis.duration_s,
        heatmap_png_url=analysis.heatmap_png_url,
        result_json_url=analysis.result_json_url,
        source=_enum_value(analysis.source),
        error=analysis.error,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
    )


def video_out(video: Video | None) -> VideoOut | None:
    if video is None:
        return None
    return VideoOut(
        provider=video.provider,
        provider_video_id=video.provider_video_id,
        title=video.title,
        channel_title=video.channel_title,
        duration_s=video.duration_s,
        view_count=video.view_count,
        published_at=video.published_at,
    )
