import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import type { ApiProjectDetail, ApiProjectStatus } from "@/lib/api/contracts";
import { laravelInternalFetch } from "@/lib/server/laravel";
import { Badge } from "@/ui/primitives/Badge";
import { Button } from "@/ui/primitives/Button";
import { buttonStyles } from "@/ui/primitives/buttonStyles";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/ui/primitives/Card";
import { Skeleton } from "@/ui/primitives/skeleton";
import { CopyButton } from "@/ui/shell/CopyButton";
import { PageHeader } from "@/ui/shell/PageHeader";
import { PipelineProgress } from "@/ui/shell/PipelineProgress";

type ProjectStatus = ApiProjectStatus;

const stages = [
  "download",
  "extract_audio",
  "transcribe",
  "align",
  "segment",
  "titles",
  "render_clips",
  "done",
] as const;
const knownStages = new Set(stages);

type Stage = (typeof stages)[number];

export default async function ProjectDetailsPage({
  params,
}: {
  // params is a promise in Next.js async route handlers — await it.
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  const t = await getTranslations("project");

  const res = await laravelInternalFetch(`/api/projects/${encodeURIComponent(id)}`);
  if (res.status === 404) {
    notFound();
  }
  if (!res.ok) {
    throw new Error('Failed to load project.');
  }

  const project = (await res.json()) as ApiProjectDetail;

  const status: ProjectStatus = project.status;
  const stage: Stage = ((): Stage => {
    const s = project.stage;
    if (s && knownStages.has(s as Stage)) {
      return s as Stage;
    }

    if (status === "completed") return "done";
    if (status === "queued") return "download";
    return "transcribe";
  })();

  const progress = project.progress_percent ?? (status === "completed" ? 100 : 0);

  const stageLabel = t(`stages.${stage}`);

  const clips = project.clips.map((c) => {
    const durationSeconds = c.duration_seconds ? Math.round(c.duration_seconds) : 0;
    const labelId = c.external_id ?? c.id;

    return {
      id: c.id,
      labelId,
      score: c.score ?? 0,
      durationSeconds,
      subtitlesEnabled: Boolean(project.options.subtitles_enabled),
      status: c.status,
      viralTitle: c.title ?? labelId,
      videoUrl: c.status === "ready" && c.video_path ? `/api/clips/${c.id}/video` : "",
    };
  });

  const events = [...project.events]
    .reverse()
    .map((e) => {
      const d = e.created_at ? new Date(e.created_at) : null;
      const ts = d
        ? new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(d)
        : "—";

      return {
        ts,
        message: e.message ?? e.type,
      };
    });

  return (
    <div className="space-y-6">
      <PageHeader
        title={project.name}
        description={project.youtube_url}
        actions={
          <>
            <Link
              href={`/${locale}/projects`}
              className={buttonStyles({ variant: "ghost", size: "sm" })}
            >
              {t("back")}
            </Link>
            <StatusBadge
              status={status}
              labels={{
                queued: t("status.queued"),
                processing: t("status.processing"),
                completed: t("status.completed"),
                failed: t("status.failed"),
              }}
            />
            <Button disabled>{t("actions.retry")}</Button>
            <Button variant="danger" disabled>
              {t("actions.delete")}
            </Button>
          </>
        }
      />

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("overview.title")}</CardTitle>
            <CardDescription>{t("overview.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-[color:var(--border)] bg-[var(--surface-muted)] p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-medium text-[var(--text-muted)]">
                    {t("overview.stage")}
                  </div>
                  <div className="mt-1 text-sm font-semibold text-[var(--text)]">
                    {stageLabel}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-medium text-[var(--text-muted)]">
                    {t("overview.progress")}
                  </div>
                  <div className="mt-1 text-sm font-semibold text-[var(--text)]">
                    {progress}%
                  </div>
                </div>
              </div>
              <div className="mt-4">
                <PipelineProgress
                  value={progress}
                  stages={stages.map((s) => ({
                    key: s,
                    label: t(`stages.${s}`),
                    status:
                      status === "failed" && s === stage
                        ? "failed"
                        : stages.indexOf(s) < stages.indexOf(stage)
                          ? "done"
                          : s === stage
                            ? "active"
                            : "pending",
                  }))}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("artifacts.title")}</CardTitle>
            <CardDescription>{t("artifacts.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2">
              <ArtifactLink
                href={`/api/projects/${project.id}/artifacts/transcript`}
                label="transcript.json"
                enabled={Boolean(project.artifacts.transcript_json_path)}
              />
              <ArtifactLink
                href={`/api/projects/${project.id}/artifacts/subtitles`}
                label="subtitles.srt"
                enabled={Boolean(project.artifacts.subtitles_srt_path)}
              />
              <ArtifactLink
                href={`/api/projects/${project.id}/artifacts/clips`}
                label="clips.json"
                enabled={Boolean(project.artifacts.clips_json_path)}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("events.title")}</CardTitle>
            <CardDescription>{t("events.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            {events.length === 0 ? (
              <div className="text-sm text-[var(--text-muted)]">{t("events.empty")}</div>
            ) : (
              <div className="space-y-3">
                {events.map((e, idx) => (
                  <div key={idx} className="flex gap-3">
                    <div className="w-14 shrink-0 text-xs font-medium text-[var(--text-muted)]">
                      {e.ts}
                    </div>
                    <div className="min-w-0 flex-1 rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-3 text-sm text-[var(--text-muted)]">
                      {e.message}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("clips.title")}</CardTitle>
            <CardDescription>{t("clips.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            {clips.length === 0 ? (
              <div className="text-sm text-[var(--text-muted)]">{t("clips.empty")}</div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {clips.map((c) => (
                  <div
                    key={c.id}
                    className="w-full max-w-[360px] rounded-xl border border-[color:var(--border)] bg-[var(--surface)] p-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-[var(--text)]">
                          {c.viralTitle}
                        </div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-[var(--text-muted)]">
                          <span>{c.labelId}</span>
                          <span aria-hidden="true">•</span>
                          <span>{formatDuration(c.durationSeconds)}</span>
                          <span aria-hidden="true">•</span>
                          <span>{Math.round(c.score * 100)}%</span>
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-2">
                        <Badge variant={c.status === "ready" ? "success" : "warning"}>
                          {t(`clipStatus.${c.status}`)}
                        </Badge>
                        <Badge variant="secondary">
                          {c.subtitlesEnabled
                            ? t("clips.subtitles.on")
                            : t("clips.subtitles.off")}
                        </Badge>
                      </div>
                    </div>

                    <div className="mt-3 overflow-hidden rounded-xl border border-[color:var(--border)] bg-[var(--surface-muted)]">
                      <div className="aspect-[9/16]">
                        {c.videoUrl ? (
                          <video
                            controls
                            preload="metadata"
                            src={c.videoUrl}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <Skeleton className="h-full w-full rounded-none" />
                        )}
                      </div>
                    </div>

                    <div className="mt-3 grid gap-2">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-xs font-medium text-[var(--text-muted)]">
                          {t("clips.titleSuggestion")}
                        </div>
                        <CopyButton
                          text={c.viralTitle}
                          label={t("clips.copyTitle")}
                          copiedLabel={t("clips.copied")}
                        />
                      </div>
                      <div className="text-sm font-medium text-[var(--text)]">{c.viralTitle}</div>
                      <Link
                        href={`/${locale}/clips/${c.id}`}
                        className={buttonStyles({ variant: "ghost", size: "sm" })}
                      >
                        {t("clips.open")}
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatusBadge({
  status,
  labels,
}: {
  status: ProjectStatus;
  labels: Record<ProjectStatus, string>;
}) {
  const variant =
    status === "completed"
      ? "success"
      : status === "failed"
        ? "danger"
        : status === "processing"
          ? "warning"
          : "secondary";

  return <Badge variant={variant}>{labels[status]}</Badge>;
}

function formatDuration(totalSeconds: number) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function ArtifactLink({
  href,
  label,
  enabled,
}: {
  href: string;
  label: string;
  enabled: boolean;
}) {
  const className =
    "w-full rounded-lg border border-[color:var(--border)] bg-[var(--surface)] px-3 py-2 text-left text-sm transition-colors motion-reduce:transition-none";

  if (!enabled) {
    return <div className={className + " text-[var(--text-muted)] opacity-60"}>{label}</div>;
  }

  return (
    <a
      href={href}
      className={
        className +
        " text-[var(--text-muted)] hover:bg-[var(--surface-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
      }
    >
      {label}
    </a>
  );
}
