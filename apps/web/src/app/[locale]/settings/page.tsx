import { getTranslations } from 'next-intl/server';

import { Badge } from '@/ui/primitives/Badge';
import { Button } from '@/ui/primitives/Button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/ui/primitives/Card';
import { Input } from '@/ui/primitives/Input';
import { PageHeader } from '@/ui/shell/PageHeader';
import { ThemeSegmentedControl } from '@/ui/theme/ThemeSegmentedControl';

export default async function SettingsPage() {
  const t = await getTranslations('settings');

  return (
    <div className="space-y-6">
      <PageHeader title={t('title')} description={t('subtitle')} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>{t('profile.title')}</CardTitle>
                <CardDescription>{t('profile.subtitle')}</CardDescription>
              </div>
              <Badge>{t('profile.badge')}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              <Field label={t('profile.nameLabel')} defaultValue="Demo User" />
              <Field label={t('profile.emailLabel')} defaultValue="demo@youtok.com" />
            </div>
          </CardContent>
          <CardFooter>
            <Button variant="primary">{t('profile.save')}</Button>
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('workspace.title')}</CardTitle>
            <CardDescription>{t('workspace.subtitle')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              <Field label={t('workspace.slugLabel')} defaultValue="demo.youtok.com" />

              <div className="rounded-lg border border-[color:var(--border)] bg-[var(--surface-muted)] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-[var(--text)]">{t('workspace.notificationsTitle')}</div>
                    <div className="mt-1 text-sm text-[var(--text-muted)]">{t('workspace.notificationsHint')}</div>
                  </div>
                  <label className="relative inline-flex cursor-pointer items-center">
                    <input type="checkbox" defaultChecked className="peer sr-only" />
                    <div className="h-6 w-11 rounded-full bg-[color:var(--border)] transition-colors peer-checked:bg-[var(--accent)]" />
                    <div className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-[var(--surface)] shadow-sm transition-transform peer-checked:translate-x-5" />
                  </label>
                </div>
              </div>
            </div>
          </CardContent>
          <CardFooter>
            <Button>{t('workspace.save')}</Button>
          </CardFooter>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>{t('theme.title')}</CardTitle>
            <CardDescription>{t('theme.subtitle')}</CardDescription>
          </CardHeader>
          <CardContent>
            <ThemeSegmentedControl />
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t('danger.title')}</CardTitle>
            <CardDescription>{t('danger.subtitle')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <div className="text-sm font-medium text-[var(--text)]">{t('danger.actionTitle')}</div>
                <div className="mt-1 text-sm text-[var(--text-muted)]">{t('danger.actionHint')}</div>
              </div>
              <Button variant="danger">{t('danger.action')}</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Field({ label, defaultValue }: { label: string; defaultValue: string }) {
  return (
    <label className="grid gap-2">
      <span className="text-xs font-medium text-[var(--text-muted)]">{label}</span>
      <Input defaultValue={defaultValue} />
    </label>
  );
}
