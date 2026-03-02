import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/ui/shell/PageHeader";

import { ClipsIndex } from "./ui/ClipsIndex";

export default async function ClipsPage() {
  const t = await getTranslations("clips");

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("subtitle")} />

      <ClipsIndex />
    </div>
  );
}
