import { useEffect, type ReactNode } from "react";
import { useUi } from "../i18n";
import { PageTransition, TransitionLink } from "../navigation";
import { Eyebrow } from "./ui";

export function ArchivePage({ children, title }: { children: ReactNode; title: string }) {
  useEffect(() => {
    document.title = `Arkwaifu | ${title}`;
  }, [title]);

  return <PageTransition>{children}</PageTransition>;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  meta,
  titleLanguage,
  descriptionLanguage,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  meta?: ReactNode;
  titleLanguage?: string;
  descriptionLanguage?: string;
}) {
  return (
    <header className="grid border-b-[3px] border-ink pb-[clamp(2rem,5vw,4rem)]">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h1
        className="mb-6 max-w-[14ch] font-display text-[clamp(3.4rem,8vw,7.5rem)] leading-[0.88] font-black tracking-[-0.035em] uppercase max-sm:text-[clamp(3rem,15vw,5.5rem)]"
        lang={titleLanguage}
      >
        {title}
      </h1>
      {description ? (
        <p
          className="mb-6 max-w-3xl text-[clamp(1.05rem,1.8vw,1.35rem)] leading-[1.55] text-ink/80"
          lang={descriptionLanguage}
        >
          {description}
        </p>
      ) : null}
      {meta ? (
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs font-bold tracking-[0.05em] uppercase [&>*]:[overflow-wrap:anywhere]">
          {meta}
        </div>
      ) : null}
    </header>
  );
}

export function BackLink({ children, to }: { children: ReactNode; to: string }) {
  return (
    <TransitionLink
      className="mb-8 inline-flex min-h-11 items-center gap-2 text-xs font-extrabold tracking-[0.04em] uppercase underline decoration-2 underline-offset-4 before:content-['←'] hover:bg-brand-soft"
      to={to}
      transition="back"
    >
      {children}
    </TransitionLink>
  );
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  const { t } = useUi();

  return (
    <section className="mt-12 border-2 border-ink bg-surface p-[clamp(2rem,5vw,4rem)]">
      <Eyebrow>{t("empty.eyebrow")}</Eyebrow>
      <h2 className="mb-4 text-[clamp(1.7rem,4vw,3.2rem)] font-black uppercase">{title}</h2>
      <p className="mb-0 max-w-2xl leading-relaxed text-muted">{children}</p>
    </section>
  );
}
