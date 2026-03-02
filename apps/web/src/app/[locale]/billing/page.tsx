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
import { Progress } from '@/ui/primitives/Progress';
import { Skeleton } from '@/ui/primitives/skeleton';
import { PageHeader } from '@/ui/shell/PageHeader';

export default async function BillingPage() {
  const t = await getTranslations('billing');

  const included = 200;
  const used = 42;
  const usage = Math.round((used / included) * 100);

  return (
    <div className="space-y-6">
      <PageHeader title={t('title')} description={t('subtitle')} />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>{t('plan.title')}</CardTitle>
                <CardDescription>{t('plan.subtitle')}</CardDescription>
              </div>
              <Badge variant="warning">{t('plan.badge')}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <div className="text-3xl font-semibold tracking-tight">$19</div>
                <div className="mt-1 text-sm text-[var(--text-muted)]">{t('plan.priceHint')}</div>
              </div>

              <div className="flex items-center gap-2">
                <Button variant="primary">{t('plan.upgrade')}</Button>
                <Button>{t('plan.manage')}</Button>
              </div>
            </div>

            <div className="mt-5 rounded-lg border border-[color:var(--border)] bg-[var(--surface-muted)] p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium text-[var(--text)]">{t('usage.title')}</div>
                <div className="text-sm text-[var(--text-muted)]">
                  {t('usage.value', { used, included })}
                </div>
              </div>
              <div className="mt-3">
                <Progress value={usage} />
                <div className="mt-2 text-xs text-[var(--text-muted)]">{t('usage.hint')}</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('payment.title')}</CardTitle>
            <CardDescription>{t('payment.subtitle')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-3">
                <div className="text-xs font-medium text-[var(--text-muted)]">{t('payment.methodLabel')}</div>
                <div className="mt-1 text-sm font-medium text-[var(--text)]">Visa •••• 4242</div>
              </div>
              <div className="rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-3">
                <div className="text-xs font-medium text-[var(--text-muted)]">{t('payment.billingEmailLabel')}</div>
                <div className="mt-1 text-sm text-[var(--text)]">billing@youtok.com</div>
              </div>
            </div>
          </CardContent>
          <CardFooter>
            <Button className="w-full">{t('payment.update')}</Button>
          </CardFooter>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('invoices.title')}</CardTitle>
          <CardDescription>{t('invoices.subtitle')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3 text-xs font-medium text-[var(--text-muted)]">
              <div>{t('invoices.colDate')}</div>
              <div>{t('invoices.colAmount')}</div>
              <div className="text-right">{t('invoices.colStatus')}</div>
            </div>

            <div className="space-y-2">
              <div className="grid grid-cols-3 items-center gap-3 rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
                <div className="flex justify-end">
                  <Skeleton className="h-6 w-20 rounded-full" />
                </div>
              </div>
              <div className="grid grid-cols-3 items-center gap-3 rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
                <div className="flex justify-end">
                  <Skeleton className="h-6 w-20 rounded-full" />
                </div>
              </div>
              <div className="grid grid-cols-3 items-center gap-3 rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
                <div className="flex justify-end">
                  <Skeleton className="h-6 w-20 rounded-full" />
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
