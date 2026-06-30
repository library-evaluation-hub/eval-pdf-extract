const API_BASE = "/api";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface RunInfo {
  run_id: string;
  started_at: string;
  completed_at: string;
  total_pairs: number;
  completed: number;
  failed: number;
  config: Record<string, unknown>;
}

export interface AdapterInfo {
  id: string;
  command: string;
  language: string;
  timeout_seconds: number;
  supports_ocr: boolean;
  disabled: boolean;
  implemented: boolean;
}

export interface FixtureInfo {
  id: string;
  path: string;
  category: string;
  expected_page_count: number;
  sha256: string;
  tags: string[];
  difficulty: string | null;
}

export interface ScoreRow {
  adapter_id: string;
  fixture_id: string;
  fixture_category: string;
  metric: string;
  value: number | null;
  value_text: string | null;
  skipped: number;
}

export interface LeaderboardEntry {
  adapter_id: string;
  [metric: string]: string | number | null;
}

export interface PageData {
  page_number: number;
  width: number;
  height: number;
  text: string;
  blocks: Array<Record<string, unknown>>;
  tables: Array<Record<string, unknown>>;
}

export interface ResultData {
  schema_version: string;
  metadata: Record<string, unknown>;
  pages: PageData[];
}

export interface ScoreData {
  adapter_id: string;
  fixture_id: string;
  fixture_category: string;
  metrics: Record<string, unknown>;
  skipped_metrics: string[];
}

export interface AdapterResultEntry {
  run_id: string;
  adapter_id: string;
  fixture_id: string;
  result: ResultData | null;
  score: ScoreData | null;
  stderr: string;
}

export interface FixtureDetail extends FixtureInfo {
  expected: ResultData | null;
  adapter_results: AdapterResultEntry[];
}

export interface AdapterDetail extends AdapterInfo {
  fixture_scores: Array<{
    fixture_id: string;
    fixture_category: string;
    run_id: string;
    metrics: Record<string, unknown>;
  }>;
}

export interface CompareAdapterResult {
  run_id: string;
  adapter_id: string;
  result: ResultData | null;
  score: ScoreData | null;
}

export interface CompareFixture {
  fixture_id: string;
  expected: ResultData | null;
  adapter_results: Record<string, CompareAdapterResult>;
}

export interface CompareData {
  run_ids: string[];
  fixtures: CompareFixture[];
}

export const api = {
  health: () => fetchJSON<{ status: string }>("/health"),
  listRuns: () => fetchJSON<RunInfo[]>("/runs"),
  getRun: (runId: string) => fetchJSON<RunInfo>(`/runs/${runId}`),
  getRunScores: (runId: string) => fetchJSON<ScoreRow[]>(`/runs/${runId}/scores`),
  getRunLeaderboard: (runId: string) => fetchJSON<LeaderboardEntry[]>(`/runs/${runId}/leaderboard`),
  listAdapters: () => fetchJSON<AdapterInfo[]>("/adapters"),
  getAdapter: (adapterId: string) => fetchJSON<AdapterDetail>(`/adapters/${adapterId}`),
  listFixtures: () => fetchJSON<FixtureInfo[]>("/fixtures"),
  getFixture: (fixtureId: string) => fetchJSON<FixtureDetail>(`/fixtures/${fixtureId}`),
  getCompare: (runIds: string[], fixtures: string[], adapters: string[]) =>
    fetchJSON<CompareData>(
      `/compare?run_ids=${encodeURIComponent(runIds.join(","))}&fixtures=${encodeURIComponent(fixtures.join(","))}&adapters=${encodeURIComponent(adapters.join(","))}`,
    ),
};

export const METRIC_IDS = [
  "text_cer",
  "text_wer",
  "text_exact_page_match_ratio",
  "table_detection_f1",
  "table_cell_value_f1",
  "heading_detection_f1",
  "reading_order_kendall_tau",
  "wall_time_ms",
  "peak_memory_mb",
  "output_size_kb",
  "success",
  "partial_completion_ratio",
  "error_category",
] as const;

export const METRIC_CATEGORIES: Record<string, string> = {
  text_cer: "text",
  text_wer: "text",
  text_exact_page_match_ratio: "text",
  table_detection_f1: "structure",
  table_cell_value_f1: "structure",
  heading_detection_f1: "structure",
  reading_order_kendall_tau: "structure",
  wall_time_ms: "performance",
  peak_memory_mb: "performance",
  output_size_kb: "performance",
  success: "robustness",
  partial_completion_ratio: "robustness",
  error_category: "robustness",
};
