import Link from "next/link";
import { getTranslations } from "next-intl/server";

import type { ApiProjectsIndexResponse, ApiProjectStatus } from "@/lib/api/contracts";
import { laravelInternalFetch } from "@/lib/server/laravel";
import { Badge } from "@/ui/primitives/Badge";
import { buttonStyles } from "@/ui/primitives/buttonStyles";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/ui/primitives/Card";
import { EmptyState } from "@/ui/shell/EmptyState";
import { PageHeader } from "@/ui/shell/PageHeader";

export default async function DashboardPage({
  params,
}: {
  // Next.js requires awaiting the `params` object when using async
  // components in dynamic routes; accessing `params.locale` directly
  // triggers the runtime warning seen earlier.
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations("dashboard");

  const res = await laravelInternalFetch("/api/projects");
  if (!res.ok) {
    throw new Error('Failed to load projects.');
  }
  const json = (await res.json()) as ApiProjectsIndexResponse;
  const projects = json.data;

  const counts = projects.reduce(
    (acc, p) => {
      acc[p.status] += 1;
      return acc;
    },
    {
      queued: 0,
      processing: 0,
      completed: 0,
      failed: 0,
    } satisfies Record<ApiProjectStatus, number>
  );

  const latest = projects.slice(0, 5);

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("subtitle")} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label={t("kpi.queued")} value={String(counts.queued)} />
        <KpiCard label={t("kpi.processing")} value={String(counts.processing)} />
        <KpiCard label={t("kpi.completed")} value={String(counts.completed)} />
        <KpiCard label={t("kpi.failed")} value={String(counts.failed)} />
      </div>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>{t("latest.title")}</CardTitle>
            <div className="mt-1 text-sm text-[var(--text-muted)]">{t("latest.subtitle")}</div>
          </div>

          <Link
            href={`/${locale}/projects/new`}
            className={buttonStyles({ variant: "primary", size: "sm" })}
          >
            {t("latest.new")}
          </Link>
        </CardHeader>

        <CardContent>
          {latest.length === 0 ? (
            <EmptyState
              title={t("latest.empty")}
              actionLabel={t("latest.new")}
              actionHref={`/${locale}/projects/new`}
            />
          ) : (
            <div className="divide-y divide-[color:var(--border)] overflow-hidden rounded-lg border border-[color:var(--border)] bg-[var(--surface)]">
              {latest.map((p) => (
                <Link
                  key={p.id}
                  href={`/${locale}/projects/${p.id}`}
                  className="flex items-center justify-between gap-4 px-4 py-3 text-sm transition-colors hover:bg-[var(--surface-muted)] motion-reduce:transition-none"
                >
                  <div className="min-w-0">
                    <div className="truncate font-medium text-[var(--text)]">{p.name}</div>
                    <div className="mt-0.5 truncate text-xs text-[var(--text-muted)]">{p.id}</div>
                  </div>
                  <StatusBadge
                    status={p.status}
                    labels={{
                      queued: t("kpi.queued"),
                      processing: t("kpi.processing"),
                      completed: t("kpi.completed"),
                      failed: t("kpi.failed"),
                    }}
                  />
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[color:var(--border)] bg-[var(--surface)] p-4 shadow-sm transition-all hover:-translate-y-px hover:shadow motion-reduce:transition-none motion-reduce:hover:translate-y-0">
      <div className="text-xs font-medium text-[var(--text-muted)]">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-[var(--text)]">{value}</div>
    </div>
  );
}

function StatusBadge({
  status,
  labels,
}: {
  status: ApiProjectStatus;
  labels: Record<ApiProjectStatus, string>;
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
