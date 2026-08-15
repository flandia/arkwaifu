import { useParams } from "react-router";
import { useUi } from "../i18n";
import { requiredLocale } from "../navigation";
import { ArchivePage, PageHeader } from "../shared/Page";
import { ActionLink } from "../shared/ui/Action";
import { Eyebrow } from "../shared/ui/Typography";

export function AboutPage() {
  const { t } = useUi();
  const locale = requiredLocale(useParams().locale);

  return (
    <ArchivePage
      canonicalPath="/CN/about"
      description={t("about.description")}
      title={t("about.title")}
    >
      <PageHeader
        description={t("about.description")}
        eyebrow={t("about.eyebrow")}
        title={t("about.pageTitle")}
      />
      <div className="mt-16 grid gap-[clamp(2rem,6vw,6rem)] min-[56rem]:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
        <section>
          <h2 className="mb-6 text-[clamp(2rem,4vw,4rem)] leading-none font-black tracking-tight uppercase">
            {t("about.holdsTitle")}
          </h2>
          <p className="max-w-3xl text-lg leading-loose">{t("about.holdsBody")}</p>
          <p className="max-w-3xl text-lg leading-loose">
            {t("about.feedbackBeforeIssue")}
            <a
              className="font-extrabold underline decoration-2 underline-offset-4 hover:bg-signal"
              href="https://github.com/flandia/arkwaifu/issues"
              rel="noreferrer"
              target="_blank"
            >
              Issue
            </a>
            {t("about.feedbackBetweenLinks")}
            <a
              className="font-extrabold underline decoration-2 underline-offset-4 hover:bg-signal"
              href="https://github.com/flandia/arkwaifu/pulls"
              rel="noreferrer"
              target="_blank"
            >
              PR
            </a>
            {t("about.feedbackAfterPullRequest")}
          </p>
        </section>
        <aside className="self-start border-[3px] border-ink bg-brand p-8 text-white shadow-hard">
          <Eyebrow className="text-white/70">{t("about.startReading")}</Eyebrow>
          <h2 className="mb-6 text-[clamp(2rem,4vw,3.5rem)] leading-none font-black tracking-tight uppercase">
            {t("about.followIndex")}
          </h2>
          <p className="mb-7 text-lg leading-relaxed text-white/80">{t("about.followBody")}</p>
          <ActionLink className="bg-surface text-ink" adornment="forward" to={`/${locale}/scores`}>
            {t("about.openMain")}
          </ActionLink>
        </aside>
      </div>
      <section className="mt-[clamp(4rem,9vw,8rem)] border-t-[3px] border-ink pt-12">
        <h2 className="mb-6 text-[clamp(2rem,4vw,4rem)] leading-none font-black tracking-tight uppercase">
          {t("about.credits")}
        </h2>
        <p className="max-w-4xl text-lg leading-loose">
          {t("about.maintainerLabel")}
          <a
            className="font-extrabold underline decoration-2 underline-offset-4 hover:bg-signal"
            href="https://github.com/flandia"
            rel="noreferrer"
            target="_blank"
          >
            @flandia
          </a>
          {t("about.maintainerAfter")}
          {t("about.softwareRightsBefore")}
          <a
            className="font-extrabold underline decoration-2 underline-offset-4 hover:bg-signal"
            href="https://github.com/flandia/arkwaifu"
            rel="noreferrer"
            target="_blank"
          >
            flandia/arkwaifu
          </a>
          {t("about.softwareRightsAfter")}
          {t("about.assetRights")}
        </p>
      </section>
    </ArchivePage>
  );
}
