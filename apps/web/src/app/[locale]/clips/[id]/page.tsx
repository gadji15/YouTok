import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import type { ApiClipDetail } from "@/lib/api/contracts";
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
import { Progress } from "@/ui/primitives/Progress";
import { Skeleton } from "@/ui/primitives/skeleton";
import { PageHeader } from "@/ui/shell/PageHeader";

export default async function ClipDetailsPage({
  params,
}: {
  // params is a promise in Next.js async route handlers — await it.
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  const t = await getTranslations("clip");

  const res = await laravelInternalFetch(`/api/clips/${encodeURIComponent(id)}`);
  if (res.status === 404) {
    notFound();
  }
  if (!res.ok) {
    throw new Error('Failed to load clip.');
  }

  const clip = (await res.json()) as ApiClipDetail;

  const status = clip.status;

  const progressValue = status === "pending" ? 0 : 100;
  const progressVariant =
    status === "failed" ? "danger" : status === "ready" ? "success" : "warning";

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("title", { id })}
        description={clip.project ? clip.project.name : t("subtitle")}
        actions={
          <>
            <Link
              href={`/${locale}/clips`}
              className={buttonStyles({ variant: "ghost", size: "sm" })}
            >
              {t("back")}
            </Link>
            <Badge
              variant={
                status === "ready" ? "success" : status === "failed" ? "danger" : "warning"
              }
            >
              {t(`status.${status}`)}
            </Badge>
            <Button variant="primary" disabled={!clip.video_path}>
              {t("actions.download")}
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("preview.title")}</CardTitle>
            <CardDescription>{t("preview.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-hidden rounded-xl border border-[color:var(--border)] bg-[var(--surface-muted)]">
              <div className="aspect-video">
                {status === "ready" && clip.video_path ? (
                  <video
                    controls
                    preload="metadata"
                    src={`/api/clips/${id}/video`}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <Skeleton className="h-full w-full rounded-none" />
                )}
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-[color:var(--border)] bg-[var(--surface-muted)] p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium text-[var(--text)]">
                  {t("progress.title")}
                </div>
                <div className="text-sm text-[var(--text-muted)]">
                  {t("progress.value", { value: progressValue })}
                </div>
              </div>
              <div className="mt-3">
                <Progress value={progressValue} variant={progressVariant} />
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("meta.title")}</CardTitle>
              <CardDescription>{t("meta.subtitle")}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 text-sm">
                <MetaRow label={t("meta.clipId")} value={id} />
                <MetaRow label={t("meta.created")} value={clip.created_at ?? "—"} />
                <MetaRow
                  label={t("meta.duration")}
                  value={
                    clip.duration_seconds !== null
                      ? formatDuration(Math.round(clip.duration_seconds))
                      : "—"
                  }
                />
                <MetaRow label={t("meta.format")} value="mp4" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("actions.title")}</CardTitle>
              <CardDescription>{t("actions.subtitle")}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2">
                <Button disabled>{t("actions.copyLink")}</Button>
                <Button disabled>{t("actions.openInNewTab")}</Button>
                <a
                  href={`/api/clips/${id}/subtitles/srt`}
                  className={buttonStyles({ variant: "secondary" })}
                >
                  .srt
                </a>
                <a
                  href={`/api/clips/${id}/subtitles/ass`}
                  className={buttonStyles({ variant: "secondary" })}
                >
                  .ass
                </a>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="text-[var(--text-muted)]">{label}</div>
      <div className="truncate font-medium text-[var(--text)]">{value}</div>
    </div>
  );
}

function formatDuration(totalSeconds: number) {
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}
