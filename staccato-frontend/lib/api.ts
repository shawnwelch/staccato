// Typed client for the Staccato backend public API.
// All fetches are server-side, cached for 60s, and fail soft: helpers return
// null (or a NotFound marker) instead of throwing, so every page renders even
// when the backend is unreachable (e.g. at build time).

export type AnalysisStatus = "queued" | "running" | "complete" | "failed";
export type PacingLabel = "calm" | "moderate" | "fast" | "hyper-paced";
export type Trend = "speeding_up" | "stable" | "slowing_down";

export interface Analysis {
  id: string;
  status: AnalysisStatus;
  engine_version: string;
  score: number | null;
  label: PacingLabel | null;
  median_shot_s: number | null;
  cuts_per_minute: number | null;
  cut_count: number | null;
  duration_s: number | null;
  heatmap_png_url: string | null;
  result_json_url: string | null;
  source: "url" | "upload" | "optical";
  created_at: string;
  completed_at: string | null;
}

export interface Video {
  provider: "youtube";
  provider_video_id: string;
  title: string | null;
  channel_title: string | null;
  duration_s: number | null;
  view_count: number | null;
  published_at: string | null;
}

export interface SharePage {
  slug: string;
  view_count: number;
  analysis: Analysis;
  video: Video | null;
}

export interface VideoPage {
  video: Video;
  analysis: Analysis | null;
}

export interface SeriesPoint {
  provider_video_id: string;
  title: string | null;
  score: number;
  view_count: number | null;
  published_at: string | null;
}

export interface ChannelScore {
  score: number;
  trend: Trend;
  n_videos: number;
  engine_version: string;
  computed_at: string;
  series: SeriesPoint[];
}

export interface Channel {
  id: string;
  provider_channel_id: string;
  title: string;
  subscriber_count: number | null;
  category: string | null;
  score: ChannelScore | null;
}

export interface LeaderboardItem {
  rank: number;
  channel_id: string;
  title: string;
  category: string | null;
  subscriber_count: number | null;
  score: number;
  trend: Trend;
  n_videos: number;
  computed_at: string;
}

export interface Leaderboard {
  items: LeaderboardItem[];
  page: number;
  page_size: number;
  total: number;
  categories: string[];
}

export const BACKEND_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_BACKEND_URL ??
  "http://localhost:8000";

/** Marker distinguishing a real 404 from an unreachable backend. */
export const NOT_FOUND = Symbol("not-found");
export type ApiResult<T> = T | typeof NOT_FOUND | null;

async function apiGet<T>(path: string): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      next: { revalidate: 60 },
    });
    if (res.status === 404) return NOT_FOUND;
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    // Backend unreachable (build time, outage) — render a fallback instead.
    return null;
  }
}

export function getShare(slug: string): Promise<ApiResult<SharePage>> {
  return apiGet<SharePage>(`/v1/share/${encodeURIComponent(slug)}`);
}

export function getVideo(
  provider: string,
  providerVideoId: string,
): Promise<ApiResult<VideoPage>> {
  return apiGet<VideoPage>(
    `/v1/videos/${encodeURIComponent(provider)}/${encodeURIComponent(providerVideoId)}`,
  );
}

export function getChannel(id: string): Promise<ApiResult<Channel>> {
  return apiGet<Channel>(`/v1/channels/${encodeURIComponent(id)}`);
}

export function getLeaderboard(params: {
  category?: string;
  page?: number;
  pageSize?: number;
  order?: "asc" | "desc";
}): Promise<ApiResult<Leaderboard>> {
  const qs = new URLSearchParams();
  if (params.category) qs.set("category", params.category);
  qs.set("page", String(params.page ?? 1));
  qs.set("page_size", String(params.pageSize ?? 25));
  qs.set("order", params.order ?? "desc");
  return apiGet<Leaderboard>(`/v1/leaderboard?${qs.toString()}`);
}

/** Label thresholds mirror the engine: <25 calm, <50 moderate, <75 fast. */
export function labelForScore(score: number): PacingLabel {
  if (score < 25) return "calm";
  if (score < 50) return "moderate";
  if (score < 75) return "fast";
  return "hyper-paced";
}
