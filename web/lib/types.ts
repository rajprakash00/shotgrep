export type MomentKind = "frame" | "shot_start" | "transcript";

export interface Moment {
  moment_id: string;
  asset_id: string;
  kind: MomentKind;
  start_s: number;
  end_s: number;
  thumbnail_url: string;
  snippet: string | null;
  score: number | null;
  deep_link: string;
}

export interface SearchPayload {
  query: string;
  model: {
    name: string;
    precision: string;
    revision: string;
  };
  results: Moment[];
}

export interface Asset {
  asset_id: string;
  filename: string;
  duration_s: number;
  fps: number;
  codec: string;
  status: string;
  proxy_url: string;
}
