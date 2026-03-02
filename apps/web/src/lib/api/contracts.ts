export type ApiProjectStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type ApiClipStatus = 'pending' | 'ready' | 'failed';

export type ApiProjectLanguage = 'fr' | 'en';

export type ApiPipelineEvent = {
  id: string;
  type: string;
  message: string | null;
  payload: unknown;
  created_at: string | null;
};

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
};

export type ApiProjectOptions = {
  language: ApiProjectLanguage | null;
  subtitles_enabled: boolean;
  clip_min_seconds: number;
  clip_max_seconds: number;
  subtitle_template: string | null;
};

export type ApiProjectListItem = {
  id: string;
  name: string;
  youtube_url: string;
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
  youtube_url: string;
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
  youtube_url: string;

  language?: ApiProjectLanguage | null;
  subtitles_enabled?: boolean;
  clip_min_seconds?: number;
  clip_max_seconds?: number;
  subtitle_template?: string | null;
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
  video_path: string | null;
  subtitles_ass_path: string | null;
  subtitles_srt_path: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type ApiClipsIndexResponse = {
  data: ApiClipListItem[];
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
  video_path: string | null;
  subtitles_ass_path: string | null;
  subtitles_srt_path: string | null;
  events: ApiPipelineEvent[];
  created_at: string | null;
  updated_at: string | null;
};
