import {
  useDeferredValue,
  useEffect,
  useId,
  useMemo,
  useState,
  ViewTransition,
  type ReactNode,
} from "react";
import { useLocation, useSearchParams } from "react-router";
import { useUi } from "../i18n";

type CollectionOrder = "archive" | "reverse";
type SearchValue = string | null | undefined;

interface CollectionIndex<T> {
  visible: T[];
  query: string;
  setQuery: (value: string) => void;
  order: CollectionOrder;
  setOrder: (value: CollectionOrder) => void;
}

function normalized(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function includesQuery(values: readonly SearchValue[], query: string): boolean {
  if (!query) return true;
  return values.some((value) => value?.toLocaleLowerCase().includes(query));
}

function setCollectionParam(
  searchParams: URLSearchParams,
  setSearchParams: ReturnType<typeof useSearchParams>[1],
  key: string,
  value: string,
  defaultValue = "",
): void {
  const next = new URLSearchParams(searchParams);
  if (value === defaultValue) next.delete(key);
  else next.set(key, value);
  setSearchParams(next, { replace: true });
}

export function useCollectionIndex<T>(
  records: T[],
  searchValues: (record: T) => readonly SearchValue[],
  defaultOrder: CollectionOrder = "reverse",
): CollectionIndex<T> {
  const { pathname } = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlQuery = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(urlQuery);
  const deferredQuery = useDeferredValue(normalized(query));
  const orderParam = searchParams.get("order");
  const order = orderParam === "archive" || orderParam === "reverse" ? orderParam : defaultOrder;

  useEffect(() => {
    const timeout = window.setTimeout(() => setQuery(urlQuery), 0);
    return () => window.clearTimeout(timeout);
  }, [pathname, urlQuery]);

  useEffect(() => {
    if (query === urlQuery) return;
    const timeout = window.setTimeout(
      () => setCollectionParam(searchParams, setSearchParams, "q", query),
      500,
    );
    return () => window.clearTimeout(timeout);
  }, [pathname, query, searchParams, setSearchParams, urlQuery]);

  const visible = useMemo(() => {
    const filtered = records.filter((record) => includesQuery(searchValues(record), deferredQuery));
    return order === "reverse" ? filtered.toReversed() : filtered;
  }, [deferredQuery, order, records, searchValues]);

  function setOrder(value: CollectionOrder): void {
    setCollectionParam(searchParams, setSearchParams, "order", value, defaultOrder);
  }

  return { visible, query, setQuery, order, setOrder };
}

export function CollectionControls({
  query,
  onQuery,
  order,
  onOrder,
  noun,
  count,
}: {
  query: string;
  onQuery: (value: string) => void;
  order: CollectionOrder;
  onOrder: (value: CollectionOrder) => void;
  noun: string;
  count: number;
}) {
  const { t } = useUi();
  const fieldID = useId();
  const searchID = `${fieldID}-search`;
  const orderID = `${fieldID}-order`;

  return (
    <section
      className="my-8 grid items-end gap-4 border-b-2 border-ink pb-6 md:mb-12 md:grid-cols-[minmax(15rem,1fr)_minmax(10rem,0.4fr)_auto]"
      aria-label={t("collection.filtersLabel")}
    >
      <div className="grid gap-2">
        <label
          className="text-[0.68rem] font-extrabold tracking-[0.07em] uppercase"
          htmlFor={searchID}
        >
          {t("collection.searchLabel")}
        </label>
        <input
          autoComplete="off"
          className="min-h-11 w-full rounded-none border-2 border-ink bg-surface px-3 py-2.5 text-ink"
          id={searchID}
          name="q"
          onChange={(event) => onQuery(event.currentTarget.value)}
          placeholder={t("collection.searchPlaceholder")}
          spellCheck={false}
          type="search"
          value={query}
        />
      </div>
      <div className="grid gap-2">
        <label
          className="text-[0.68rem] font-extrabold tracking-[0.07em] uppercase"
          htmlFor={orderID}
        >
          {t("collection.orderLabel")}
        </label>
        <select
          className="min-h-11 w-full rounded-none border-2 border-ink bg-surface px-3 py-2.5 text-ink"
          id={orderID}
          name="order"
          onChange={(event) => onOrder(event.currentTarget.value as CollectionOrder)}
          value={order}
        >
          <option value="reverse">{t("collection.reverseOrder")}</option>
          <option value="archive">{t("collection.archiveOrder")}</option>
        </select>
      </div>
      <ResultCount count={count} noun={noun} />
    </section>
  );
}

function ResultCount({ count, noun }: { count: number; noun: string }) {
  const { t } = useUi();

  return (
    <p
      className="m-0 pb-3 text-left text-sm font-bold tracking-[0.05em] uppercase tabular-nums md:text-right"
      aria-live="polite"
    >
      {t("collection.resultCount", { count, noun })}
    </p>
  );
}

export function AnimatedListItem({ children, id }: { children: ReactNode; id: string }) {
  return (
    <ViewTransition default="none" enter="fade-in" exit="fade-out" key={id} update="morph">
      {children}
    </ViewTransition>
  );
}
