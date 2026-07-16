export type JobStatus =
  | "todo"
  | "doing"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "aborting";

export const JOB_STATUSES: JobStatus[] = [
  "todo",
  "doing",
  "succeeded",
  "failed",
  "cancelled",
  "aborting",
];

export interface Job {
  id: number;
  queue_name: string;
  task_name: string;
  status: JobStatus;
  priority: number;
  attempts: number;
  scheduled_at: string | null;
  args: Record<string, unknown>;
}

export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface JobStats {
  by_status: Record<string, number>;
  by_queue: Record<string, number>;
}

export interface LiveSession {
  id: string;
  user_id: string;
  content_label: string;
  duration_s: number;
  cut_count: number;
  device_score: number | null;
  recomputed_score: number;
  label: string;
  promoted: boolean;
  reviewed: boolean;
  created_at: string;
}

export interface EngineDistribution {
  engine_version: string;
  count: number;
  mean_score: number | null;
  median_score: number | null;
}

export interface EngineInfo {
  current_version: string;
  distributions: EngineDistribution[];
}
