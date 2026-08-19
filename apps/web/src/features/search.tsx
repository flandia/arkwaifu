import { startTransition, useDeferredValue, useEffect, useId, useState } from "react";
import type { TFunction } from "i18next";
import { useParams, useSearchParams } from "react-router";
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
  query: string;
  results: SearchResult[];
  loading: boolean;
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
    <li className="min-w-0 [contain-intrinsic-size:auto_13rem] [content-visibility:auto]">
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

export function SearchPage() {
  const { t } = useUi();
  const locale = requiredLocale(useParams().locale);
  const [searchParams, setSearchParams] = useSearchParams();
  const urlQuery = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(urlQuery);
  const deferredQuery = useDeferredValue(query);
  const fieldID = useId();
  const [state, setState] = useState<SearchState>({
    query: "",
    results: [],
    loading: false,
    error: null,
  });

  useEffect(() => {
    setQuery(urlQuery);
  }, [urlQuery]);

  useEffect(() => {
    if (query === urlQuery) return;
    const timeout = window.setTimeout(() => {
      const next = new URLSearchParams(searchParams);
      if (query) next.set("q", query);
      else next.delete("q");
      startTransition(() => setSearchParams(next, { replace: true }));
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [query, searchParams, setSearchParams, urlQuery]);

  const normalizedQuery = deferredQuery.trim();
  useEffect(() => {
    let active = true;
    if (!normalizedQuery) {
      setState({ query: "", results: [], loading: false, error: null });
      return () => {
        active = false;
      };
    }

    setState((previous) => ({ ...previous, query: normalizedQuery, loading: true, error: null }));
    const timeout = window.setTimeout(() => {
      void getSearchResults(locale, normalizedQuery).then(
        (results) => {
          if (!active) return;
          setState({ query: normalizedQuery, results, loading: false, error: null });
        },
        (error: unknown) => {
          if (!active) return;
          setState((previous) => ({ ...previous, query: normalizedQuery, loading: false, error }));
        },
      );
    }, 250);

    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [locale, normalizedQuery]);

  if (state.error) throw state.error;

  const hasQuery = Boolean(query.trim());
  const settled = hasQuery && state.query === normalizedQuery && !state.loading;

  return (
    <ArchivePage description={t("search.description")} noIndex title={t("search.title")}>
      <PageHeader
        eyebrow={t("search.eyebrow")}
        meta={<span>{t("common.locale", { locale })}</span>}
        title={t("search.title")}
      />

      <section
        className="my-8 grid gap-3 border-b-2 border-ink pb-8 md:mb-12"
        aria-label={t("search.title")}
      >
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
          onChange={(event) => setQuery(event.currentTarget.value)}
          placeholder={t("search.placeholder")}
          spellCheck={false}
          type="search"
          value={query}
        />
        <p className="m-0 min-h-5 text-sm text-muted" aria-live="polite" aria-atomic="true">
          {state.loading
            ? t("search.loading")
            : settled
              ? t("search.resultCount", { count: state.results.length })
              : null}
        </p>
      </section>

      {!hasQuery ? (
        <EmptyState title={t("search.initial")}>{t("search.initialHint")}</EmptyState>
      ) : settled && state.results.length === 0 ? (
        <EmptyState title={t("search.noResults")}>{t("search.noResultsHint")}</EmptyState>
      ) : (
        <ol className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(min(100%,22rem),1fr))] border-t-2 border-l-2 border-ink p-0">
          {state.results.map((result, index) => (
            <SearchResultCard
              index={index}
              key={`${result.kind}:${result.category ?? ""}:${result.id}`}
              locale={locale}
              result={result}
            />
          ))}
        </ol>
      )}
    </ArchivePage>
  );
}
