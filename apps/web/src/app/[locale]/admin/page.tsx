import { getTranslations } from 'next-intl/server';

import { Badge } from '@/ui/primitives/Badge';
import { Button } from '@/ui/primitives/Button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/ui/primitives/Card';
import { PageHeader } from '@/ui/shell/PageHeader';

export default async function AdminPage() {
  const t = await getTranslations('admin');

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={<Badge>{t('badge')}</Badge>}
      />

      <Card>
        <CardHeader>
          <CardTitle>{t('placeholder.title')}</CardTitle>
          <CardDescription>{t('placeholder.subtitle')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
            <div className="text-sm text-[var(--text-muted)]">{t('placeholder.note')}</div>
            <Button disabled>{t('placeholder.cta')}</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
