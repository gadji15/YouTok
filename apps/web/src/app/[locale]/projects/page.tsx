import Link from "next/link";
import { getTranslations } from "next-intl/server";

import type { ApiProjectsIndexResponse, ApiProjectStatus } from "@/lib/api/contracts";
import { laravelInternalFetch } from "@/lib/server/laravel";
import { Badge } from "@/ui/primitives/Badge";
import { buttonStyles } from "@/ui/primitives/buttonStyles";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/primitives/Card";
import { Input } from "@/ui/primitives/Input";
import { Progress } from "@/ui/primitives/Progress";
import { PageHeader } from "@/ui/shell/PageHeader";

type ProjectStatus = ApiProjectStatus;

type ProjectRow = {
  id: string;
  name: string;
  status: ProjectStatus;
  stage: string | null;
  progress: number;
  updatedAt: string | null;
};

const knownStages = new Set([
  "download",
  "extract_audio",
  "transcribe",
  "align",
  "segment",
  "titles",
  "render_clips",
  "done",
]);

export default async function ProjectsPage({
  params,
}: {
  // params is a promise in Next.js async route handlers — await it.
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations("projects");
  const tProject = await getTranslations("project");

  const df = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  const res = await laravelInternalFetch("/api/projects");
  if (!res.ok) {
    throw new Error('Failed to load projects.');
  }
  const json = (await res.json()) as ApiProjectsIndexResponse;

  const projects: ProjectRow[] = json.data.map((p) => ({
    id: p.id,
    name: p.name,
    status: p.status,
    stage: p.stage,
    progress: p.progress_percent ?? (p.status === "completed" ? 100 : 0),
    updatedAt: p.updated_at,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={
          <Link
            href={`/${locale}/projects/new`}
            className={buttonStyles({ variant: "primary", size: "sm" })}
          >
            {t("new")}
          </Link>
        }
      />

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>{t("title")}</CardTitle>
          <div className="w-full sm:w-72">
            <Input placeholder={t("searchPlaceholder")} />
          </div>
        </CardHeader>

        <CardContent>
          <div className="overflow-hidden rounded-lg border border-[color:var(--border)] bg-[var(--surface)]">
            <div className="grid grid-cols-12 bg-[var(--surface-muted)] px-4 py-2 text-xs font-medium text-[var(--text-muted)]">
              <div className="col-span-7">{t("table.name")}</div>
              <div className="col-span-3">{t("table.status")}</div>
              <div className="col-span-2 text-right">{t("table.updated")}</div>
            </div>

            <div className="divide-y divide-[color:var(--border)]">
              {projects.map((p) => (
                <Link
                  key={p.id}
                  href={`/${locale}/projects/${p.id}`}
                  className="grid grid-cols-12 items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-[var(--surface-muted)] motion-reduce:transition-none"
                >
                  <div className="col-span-7 min-w-0">
                    <div className="truncate font-medium text-[var(--text)]">
                      {p.name}
                    </div>
                    <div className="mt-0.5 truncate text-xs text-[var(--text-muted)]">
                      {p.id}
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <Progress value={p.progress} className="h-1.5" />
                      <div className="shrink-0 text-[11px] font-medium text-[var(--text-muted)]">
                        {p.stage ? (
                          p.stage === "completed" ? (
                            tProject("stages.done")
                          ) : knownStages.has(p.stage) ? (
                            tProject(`stages.${p.stage}`)
                          ) : (
                            p.stage
                          )
                        ) : (
                          "—"
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="col-span-3">
                    <StatusBadge
                      status={p.status}
                      labels={{
                        queued: tProject("status.queued"),
                        processing: tProject("status.processing"),
                        completed: tProject("status.completed"),
                        failed: tProject("status.failed"),
                      }}
                    />
                  </div>
                  <div className="col-span-2 text-right text-xs text-[var(--text-muted)]">
                    {p.updatedAt ? df.format(new Date(p.updatedAt)) : "—"}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
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
