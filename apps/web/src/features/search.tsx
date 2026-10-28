import { startTransition, useEffect, useId, useState } from "react";
import type { TFunction } from "i18next";
import { useLocation, useNavigationType, useParams, useSearchParams } from "react-router";
import { getSearchResults } from "../api/search";
import type { Locale, SearchResult } from "../api/types";
import { useUi } from "../i18n";
import {
  archiveCategoryLabel,
  categoryLabel,
  localeLanguageTag,
  requiredLocale,
  storyParentPath,
  storyPath,
  TransitionLink,
} from "../navigation";
import { ArchivePage, EmptyState, PageHeader } from "../shared/Page";
import { Eyebrow } from "../shared/ui/Typography";

interface SearchState {
  results: SearchResult[];
  error: unknown;
}

function resultPath(locale: Locale, result: SearchResult): string | null {
  switch (result.kind) {
    case "story":
      return result.parent ? storyPath(locale, result.parent, result.id) : null;
    case "movement":
      return `/${locale}/scores/${encodeURIComponent(result.id)}`;
    case "section":
      return result.parent?.kind === "score" ? storyParentPath(locale, result.parent) : null;
    case "archive_group":
      return result.parent?.kind === "archive"
        ? `/${locale}/archives/${result.parent.archiveCategory}/${encodeURIComponent(result.id)}`
        : null;
    case "gallery":
      return `/${locale}/galleries/${encodeURIComponent(result.id)}`;
    case "narrative_asset":
      return result.category
        ? `/${locale}/assets/narrative/${result.category}/${encodeURIComponent(result.id)}`
        : null;
  }
}

function resultKindLabel(result: SearchResult, t: TFunction): string {
  if (result.kind === "narrative_asset" && result.category) {
    return `${t("search.kind.narrative_asset")} · ${categoryLabel(result.category, t)}`;
  }
  if (result.kind === "archive_group" && result.parent?.kind === "archive") {
    return `${t("search.kind.archive_group")} · ${archiveCategoryLabel(result.parent.archiveCategory, t)}`;
  }
  return t(`search.kind.${result.kind}`);
}

function SearchResultCard({
  result,
  index,
  locale,
}: {
  result: SearchResult;
  index: number;
  locale: Locale;
}) {
  const { t } = useUi();
  const path = resultPath(locale, result);
  if (!path) return null;

  return (
    <li className="min-w-0 [contain-intrinsic-block-size:auto_13rem] [content-visibility:auto]">
      <TransitionLink
        className="group grid min-h-48 grid-cols-[8rem_minmax(0,1fr)] border-r-2 border-b-2 border-ink bg-surface text-ink no-underline transition-colors hover:bg-brand-soft sm:grid-cols-[11rem_minmax(0,1fr)]"
        to={path}
        transition="forward"
      >
        <div className="relative min-h-48 overflow-hidden border-r-2 border-ink bg-brand">
          {result.previewUrl ? (
            <img
              alt=""
              className="absolute inset-0 size-full object-cover transition-transform duration-300 group-hover:scale-105 motion-reduce:transition-none motion-reduce:group-hover:scale-100"
              height="320"
              loading="lazy"
              src={result.previewUrl}
              width="320"
            />
          ) : (
            <span
              className="absolute inset-0 grid place-items-center p-3 text-center font-mono text-xs font-bold text-white/75 uppercase"
              aria-hidden="true"
            >
              {String(index + 1).padStart(3, "0")}
            </span>
          )}
        </div>
        <div className="min-w-0 p-5 sm:p-7">
          <Eyebrow className="text-muted">{resultKindLabel(result, t)}</Eyebrow>
          <h2
            className="mb-3 break-words text-[clamp(1.35rem,3vw,2.4rem)] leading-none font-black text-balance"
            lang={localeLanguageTag(locale)}
          >
            {result.title}
          </h2>
          {result.subtitle ? (
            <p className="mb-3 line-clamp-2 max-w-2xl text-sm leading-relaxed text-muted">
              {result.subtitle}
            </p>
          ) : null}
          <code className="break-all text-xs text-muted" translate="no">
            {result.id}
          </code>
        </div>
      </TransitionLink>
    </li>
  );
}

function SearchResults({ locale, query }: { locale: Locale; query: string }) {
  const { t } = useUi();
  const [request, setRequest] = useState<{
    locale: Locale;
    query: string;
    state: SearchState | null;
  }>({
    locale,
    query,
    state: null,
  });
  const current = request.locale === locale && request.query === query;
  const state = current ? request.state : null;
  if (!current) setRequest({ locale, query, state: null });

  useEffect(() => {
    if (!query) return;
    const controller = new AbortController();
    let active = true;
    const timeout = window.setTimeout(() => {
      void getSearchResults(locale, query, controller.signal).then(
        (results) => {
          if (active) setRequest({ locale, query, state: { results, error: null } });
        },
        (error: unknown) => {
          if (active) setRequest({ locale, query, state: { results: [], error } });
        },
      );
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [locale, query]);

  if (state?.error) throw state.error;
  const settled = Boolean(query) && state !== null;

  return (
    <>
      <p
        className="m-0 mb-5 min-h-5 border-b-2 border-ink pb-8 text-sm text-muted md:mb-9"
        aria-live="polite"
        aria-atomic="true"
      >
        {query && !state
          ? t("search.loading")
          : settled
            ? t("search.resultCount", { count: state!.results.length })
            : null}
      </p>
      {!query ? (
        <EmptyState title={t("search.initial")}>{t("search.initialHint")}</EmptyState>
      ) : settled && state!.results.length === 0 ? (
        <EmptyState title={t("search.noResults")}>{t("search.noResultsHint")}</EmptyState>
      ) : (
        <ol className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(min(100%,22rem),1fr))] border-t-2 border-l-2 border-ink p-0">
          {state?.results.map((result, index) => (
            <SearchResultCard
              index={index}
              key={`${result.kind}:${result.category ?? ""}:${result.id}`}
              locale={locale}
              result={result}
            />
          ))}
        </ol>
      )}
    </>
  );
}

export function SearchPage() {
  const { t } = useUi();
  const locale = requiredLocale(useParams().locale);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigationType = useNavigationType();
  const locationKey = useLocation().key;
  const urlQuery = searchParams.get("q") ?? "";
  const urlSearch = searchParams.toString();
  const [draft, setDraft] = useState<{ base: string; query: string; pending: string | null }>({
    base: locationKey,
    query: urlQuery,
    pending: null,
  });
  const sameLocation = draft.base === locationKey;
  const ownReplace = navigationType === "REPLACE" && draft.pending === urlSearch;
  const query = sameLocation || ownReplace ? draft.query : urlQuery;
  if (!sameLocation) setDraft({ base: locationKey, query, pending: null });
  const fieldID = useId();

  useEffect(() => {
    if (query === urlQuery) return;
    const timeout = window.setTimeout(() => {
      const next = new URLSearchParams(searchParams);
      if (query) next.set("q", query);
      else next.delete("q");
      setDraft((previous) => ({ ...previous, pending: next.toString() }));
      startTransition(() => setSearchParams(next, { replace: true }));
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [query, searchParams, setSearchParams, urlQuery]);

  return (
    <ArchivePage description={t("search.description")} noIndex title={t("search.title")}>
      <PageHeader
        eyebrow={t("search.eyebrow")}
        meta={<span>{t("common.locale", { locale })}</span>}
        title={t("search.title")}
      />

      <section className="mt-8 grid gap-3" aria-label={t("search.title")}>
        <label
          className="text-[0.68rem] font-extrabold tracking-[0.07em] uppercase"
          htmlFor={fieldID}
        >
          {t("search.title")}
        </label>
        <input
          autoComplete="off"
          className="min-h-14 w-full rounded-none border-2 border-ink bg-surface px-4 py-3 text-lg text-ink"
          id={fieldID}
          name="q"
          onChange={(event) => {
            const value = event.currentTarget.value;
            setDraft((previous) => ({ ...previous, base: locationKey, query: value }));
          }}
          placeholder={t("search.placeholder")}
          spellCheck={false}
          type="search"
          value={query}
        />
        <SearchResults locale={locale} query={query.trim()} />
      </section>
    </ArchivePage>
  );
}
