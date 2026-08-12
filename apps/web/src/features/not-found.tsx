import { type ReactNode } from "react";
import { useParams } from "react-router";
import { useUi } from "../i18n";
import { isLocale } from "../navigation";
import { ArchivePage } from "../shared/Page";
import { ActionLink, Eyebrow } from "../shared/ui";

export function NotFoundPage({ title, children }: { title?: string; children?: ReactNode }) {
  const { t } = useUi();
  const params = useParams();
  const locale = isLocale(params.locale) ? params.locale : "CN";
  const resolvedTitle = title ?? t("errors.notFound");
  return (
    <ArchivePage title={resolvedTitle}>
      <section className="relative min-h-[60vh] overflow-hidden pt-[clamp(3rem,8vw,7rem)]">
        <p
          className="absolute top-0 right-0 -z-10 m-0 font-display text-[clamp(10rem,30vw,30rem)] leading-[0.8] text-brand-soft"
          aria-hidden="true"
        >
          404
        </p>
        <Eyebrow>{t("errors.routeEyebrow")}</Eyebrow>
        <h1 className="mb-7 max-w-[14ch] font-display text-[clamp(3.4rem,8vw,7.5rem)] leading-[0.88] font-black tracking-tight uppercase">
          {resolvedTitle}
        </h1>
        <p className="mb-8 max-w-2xl text-lg leading-relaxed text-muted">
          {children ?? t("errors.notFoundMessage")}
        </p>
        <ActionLink adornment="back" to={`/${locale}`} transition="back">
          {t("errors.returnOverview")}
        </ActionLink>
      </section>
    </ArchivePage>
  );
}
