export type ApiProjectStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type ApiClipStatus = 'pending' | 'ready' | 'failed';

export type ApiProjectLanguage = 'fr' | 'en';
export type ApiProjectSegmentationMode = 'viral' | 'chapters';
export type ApiProjectOriginalityMode = 'none' | 'voiceover';
export type ApiProjectOutputAspect = 'vertical' | 'source';

export type ApiPipelineEvent = {
  id: string;
  type: string;
  message: string | null;
  payload: unknown;
  created_at: string | null;
};

export type ApiClipTitleCandidates = {
  provider: string | null;
  description: string | null;
  hashtags: string[];

  // Part 5 (optional)
  hooks?: string[];
  analysis?: {
    summary?: string | null;
    theme?: string | null;
    key_phrase?: string | null;
    clip_key_phrase?: string | null;
    keywords?: string[];
    signals?: string[];
    clip_phrases?: string[];
  } | null;

  candidates: { title: string; score: number; features?: Record<string, number> | null }[];
  top3: string[];
};

export type ApiClipQualitySummary = {
  template?: string | null;
  ui_safe_ymin?: number | null;
  final_overlap?: {
    measured_on?: string;
    sample_fps?: number;
    ui_safe_ymin?: number;
    face_overlap_ratio_p95?: number;
    ui_overlap_ratio_p95?: number;
  } | null;
  attempts?: unknown[] | null;
} | null;

export type ApiClip = {
  id: string;
  external_id: string | null;
  status: ApiClipStatus;
  start_seconds: number | null;
  end_seconds: number | null;
  duration_seconds: number | null;
  score: number | null;
  reason: string | null;
  title: string | null;
  title_candidates?: ApiClipTitleCandidates | null;
  quality_summary?: ApiClipQualitySummary;

  // Local/shared-volume paths returned by Laravel.
  // In production these are typically mapped to signed URLs.
  video_path: string | null;
  subtitles_ass_path: string | null;
  subtitles_srt_path: string | null;
};

export type ApiProjectArtifacts = {
  source_video_path: string | null;
  audio_path: string | null;
  transcript_json_path: string | null;
  subtitles_srt_path: string | null;
  clips_json_path: string | null;
  words_json_path: string | null;
  segments_json_path: string | null;
  source_metadata_json_path: string | null;
  source_thumbnail_path: string | null;
};

export type ApiProjectOptions = {
  language: ApiProjectLanguage | null;
  subtitles_enabled: boolean;
  clip_min_seconds: number;
  clip_max_seconds: number;
  subtitle_template: string | null;
  segmentation_mode?: ApiProjectSegmentationMode;
  originality_mode?: ApiProjectOriginalityMode;
  output_aspect?: ApiProjectOutputAspect;
};

export type ApiProjectListItem = {
  id: string;
  name: string;
  source_type: 'youtube' | 'local';
  youtube_url: string | null;
  status: ApiProjectStatus;
  stage: string | null;
  progress_percent: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type ApiProjectsIndexResponse = {
  data: ApiProjectListItem[];
};

export type ApiProjectDetail = {
  id: string;
  name: string;
  source_type: 'youtube' | 'local';
  youtube_url: string | null;
  local_video_path: string | null;
  status: ApiProjectStatus;
  stage: string | null;
  progress_percent: number | null;
  last_log_message: string | null;
  error: string | null;

  options: ApiProjectOptions;
  artifacts: ApiProjectArtifacts;
  clips: ApiClip[];
  events: ApiPipelineEvent[];

  created_at: string | null;
  updated_at: string | null;
};

export type ApiCreateProjectRequest = {
  name: string;
  youtube_url?: string;
  local_video_path?: string;

  language?: ApiProjectLanguage | null;
  subtitles_enabled?: boolean;
  clip_min_seconds?: number;
  clip_max_seconds?: number;
  subtitle_template?: string | null;
  segmentation_mode?: ApiProjectSegmentationMode;
  originality_mode?: ApiProjectOriginalityMode;
  output_aspect?: ApiProjectOutputAspect;
};

export type ApiClipListItem = {
  id: string;
  project_id: string;
  project_name: string | null;
  status: ApiClipStatus;
  start_seconds: number | null;
  end_seconds: number | null;
  duration_seconds: number | null;
  score: number | null;
  reason: string | null;
  title: string | null;
  title_candidates?: ApiClipTitleCandidates | null;
  quality_summary?: ApiClipQualitySummary;
  video_path: string | null;
  subtitles_ass_path: string | null;
  subtitles_srt_path: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type ApiClipsIndexResponse = {
  data: ApiClipListItem[];
};

export type ApiTikTokAccountStatus = 'active' | 'disabled' | 'banned';

export type ApiTikTokAccount = {
  id: string;
  username: string;
  status: ApiTikTokAccountStatus;
  notes: string | null;
};

export type ApiTikTokAccountsIndexResponse = {
  data: ApiTikTokAccount[];
};

export type ApiClipDetail = {
  id: string;
  project: { id: string; name: string } | null;
  status: ApiClipStatus;
  start_seconds: number | null;
  end_seconds: number | null;
  duration_seconds: number | null;
  score: number | null;
  reason: string | null;
  title: string | null;
  title_candidates?: ApiClipTitleCandidates | null;
  quality_summary?: ApiClipQualitySummary | null;

  tiktok_caption: string | null;
  tiktok_account_id: string | null;
  tiktok_publish_job_id: string | null;
  tiktok_publish_status: string | null;
  tiktok_publish_error: string | null;
  tiktok_published_at: string | null;

  video_path: string | null;
  subtitles_ass_path: string | null;
  subtitles_srt_path: string | null;
  events: ApiPipelineEvent[];
  created_at: string | null;
  updated_at: string | null;
};
