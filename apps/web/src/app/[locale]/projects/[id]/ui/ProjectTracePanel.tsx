'use client';

import { useEffect, useMemo, useState } from 'react';

import type { ApiProjectDetail, ApiProjectStatus } from '@/lib/api/contracts';
import { Badge } from '@/ui/primitives/Badge';
import { Button } from '@/ui/primitives/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/primitives/Card';

function msSince(iso: string | null) {
  if (!iso) return null;
  const d = new Date(iso);
  const t = d.getTime();
  if (!Number.isFinite(t)) return null;
  return Date.now() - t;
}

function formatAge(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m < 60) return `${m}m${String(r).padStart(2, '0')}s`;
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${h}h${String(mm).padStart(2, '0')}m`;
}

function statusVariant(status: ApiProjectStatus) {
  if (status === 'completed') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'processing') return 'warning';
  return 'secondary';
}

function truncateText(text: string | null | undefined, maxChars: number) {
  if (!text) return null;
  const t = String(text);
  if (t.length <= maxChars) return t;
  return `${t.slice(0, maxChars)}\n… (truncated, ${t.length} chars)`;
}

export function ProjectTracePanel({
  projectId,
  initial,
}: {
  projectId: string;
  initial: Pick<
    ApiProjectDetail,
    'status'
    | 'stage'
    | 'progress_percent'
    | 'updated_at'
    | 'last_log_message'
    | 'error'
    | 'worker_job_id'
    | 'events'
    | 'clips'
  >;
}) {
  const [data, setData] = useState(initial);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [loading, setLoading] = useState(false);
  const [lastFetchAt, setLastFetchAt] = useState<number | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  async function refreshOnce() {
    setLoading(true);
    setLastError(null);

    try {
      const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
        method: 'GET',
        cache: 'no-store',
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const json = (await res.json()) as ApiProjectDetail;
      setData({
        status: json.status,
        stage: json.stage,
        progress_percent: json.progress_percent,
        updated_at: json.updated_at,
        last_log_message: json.last_log_message,
        error: json.error,
        worker_job_id: json.worker_job_id,
        events: json.events,
        clips: json.clips,
      });
      setLastFetchAt(Date.now());
    } catch (err) {
      setLastError(err instanceof Error ? err.message : 'Failed to refresh');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!autoRefresh) return;

    const id = window.setInterval(() => {
      void refreshOnce();
    }, 10_000);

    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, projectId]);

  const updatedAge = useMemo(() => msSince(data.updated_at), [data.updated_at]);

  const blockingHint = useMemo(() => {
    if (data.status !== 'processing') return null;
    if (!updatedAge) return null;

    // Heuristic: if nothing changes for a long time, surface it.
    const thresholdMs = data.stage === 'render_clips' ? 30 * 60 * 1000 : 15 * 60 * 1000;
    if (updatedAge < thresholdMs) return null;

    return {
      severity: 'warning' as const,
      message:
        data.stage === 'render_clips'
          ? `Possible blocage: stage=render_clips depuis ${formatAge(updatedAge)}.`
          : `Possible blocage: aucune mise à jour depuis ${formatAge(updatedAge)}.`,
    };
  }, [data.stage, data.status, updatedAge]);

  const events = useMemo(() => {
    return [...data.events]
      .slice()
      .reverse()
      .map((e) => {
        const ts = e.created_at ? new Date(e.created_at).toLocaleString() : '—';
        return {
          id: e.id,
          ts,
          type: e.type,
          message: e.message ?? '',
          payload: e.payload,
        };
      });
  }, [data.events]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>Trace / Debug</CardTitle>
            <CardDescription>
              Événements pipeline + signaux de blocage (auto-refresh toutes les 10s).
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAutoRefresh((v) => !v)}
            >
              {autoRefresh ? 'Auto: ON' : 'Auto: OFF'}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void refreshOnce()}
              disabled={loading}
            >
              {loading ? 'Refresh…' : 'Refresh'}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                try {
                  const debug = {
                    copied_at: new Date().toISOString(),
                    project: {
                      id: projectId,
                      status: data.status,
                      stage: data.stage,
                      progress_percent: data.progress_percent,
                      worker_job_id: data.worker_job_id,
                      updated_at: data.updated_at,
                      last_log_message: truncateText(data.last_log_message, 6_000),
                      error: truncateText(data.error, 6_000),
                    },
                    ui: {
                      auto_refresh: autoRefresh,
                      last_fetch_at: lastFetchAt ? new Date(lastFetchAt).toISOString() : null,
                    },
                    clips: data.clips.map((c) => ({
                      id: c.external_id ?? c.id,
                      status: c.status,
                    })),
                    events: [...data.events]
                      .slice()
                      .reverse()
                      .slice(0, 30)
                      .map((e) => ({
                        type: e.type,
                        message: truncateText(e.message, 800),
                        created_at: e.created_at,
                      })),
                  };

                  await navigator.clipboard.writeText(JSON.stringify(debug, null, 2));
                  setLastError(null);
                } catch (err) {
                  setLastError(err instanceof Error ? err.message : 'Failed to copy debug');
                }
              }}
            >
              Copy debug (essentiel)
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge variant={statusVariant(data.status)}>{data.status}</Badge>
          <Badge variant="secondary">stage: {data.stage ?? '—'}</Badge>
          <Badge variant="secondary">progress: {data.progress_percent ?? 0}%</Badge>
          {data.worker_job_id ? <Badge variant="secondary">job: {data.worker_job_id}</Badge> : null}
          <span className="text-[var(--text-muted)]">
            last update: {data.updated_at ? new Date(data.updated_at).toLocaleString() : '—'}
            {updatedAge ? ` (${formatAge(updatedAge)} ago)` : ''}
          </span>
          {lastFetchAt ? (
            <span className="text-[var(--text-muted)]">last fetch: {formatAge(Date.now() - lastFetchAt)} ago</span>
          ) : null}
        </div>

        {data.last_log_message ? (
          <div className="mt-3 rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-3 text-sm">
            <div className="text-xs font-medium text-[var(--text-muted)]">last_log_message</div>
            <div className="mt-1 whitespace-pre-wrap text-[var(--text)]">{data.last_log_message}</div>
          </div>
        ) : null}

        {data.error ? (
          <div className="mt-3 rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-3 text-sm">
            <div className="text-xs font-medium text-[var(--text-muted)]">error</div>
            <div className="mt-1 whitespace-pre-wrap text-[var(--danger)]">{data.error}</div>
          </div>
        ) : null}

        {blockingHint ? (
          <div className="mt-3 rounded-lg border border-[color:var(--border)] bg-[var(--surface-muted)] p-3 text-sm">
            <div className="text-xs font-medium text-[var(--text-muted)]">signal</div>
            <div className="mt-1 text-[var(--text)]">{blockingHint.message}</div>
          </div>
        ) : null}

        {lastError ? (
          <div className="mt-3 text-sm text-[var(--danger)]">Refresh error: {lastError}</div>
        ) : null}

        <div className="mt-4">
          <div className="text-xs font-medium text-[var(--text-muted)]">Clips status</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {data.clips.map((c) => (
              <Badge key={c.id} variant={c.status === 'ready' ? 'success' : c.status === 'failed' ? 'danger' : 'warning'}>
                {c.external_id ?? c.id.slice(0, 8)}: {c.status}
              </Badge>
            ))}
          </div>
        </div>

        <div className="mt-5">
          <div className="text-xs font-medium text-[var(--text-muted)]">Pipeline events (latest first)</div>
          {events.length === 0 ? (
            <div className="mt-2 text-sm text-[var(--text-muted)]">No events yet.</div>
          ) : (
            <div className="mt-2 space-y-2">
              {events.slice(0, 50).map((e) => (
                <details
                  key={e.id}
                  className="rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-3"
                >
                  <summary className="cursor-pointer select-none text-sm text-[var(--text)]">
                    <span className="font-medium">{e.type}</span>
                    <span className="ml-2 text-xs text-[var(--text-muted)]">{e.ts}</span>
                    {e.message ? <span className="ml-2 text-xs text-[var(--text-muted)]">— {e.message}</span> : null}
                  </summary>
                  <pre className="mt-2 overflow-auto rounded-md bg-[var(--surface-muted)] p-2 text-xs text-[var(--text)]">
                    {JSON.stringify(e.payload, null, 2)}
                  </pre>
                </details>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
