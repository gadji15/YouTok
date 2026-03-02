import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { buttonStyles } from "@/ui/primitives/buttonStyles";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/primitives/Card";
import { PageHeader } from "@/ui/shell/PageHeader";

import { CreateProjectForm } from "./ui/CreateProjectForm";

export default async function NewProjectPage({
  params,
}: {
  // params is a promise in Next.js async route handlers — await it.
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations("projectNew");

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={
          <Link
            href={`/${locale}/projects`}
            className={buttonStyles({ variant: "ghost", size: "sm" })}
          >
            {t("back")}
          </Link>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <CreateProjectForm redirectLocale={locale} />
        </CardContent>
      </Card>
    </div>
  );
}
