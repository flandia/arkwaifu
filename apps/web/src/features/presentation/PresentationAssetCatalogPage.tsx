import { use } from "react";
import { useLocation, useParams, useSearchParams } from "react-router";
import { getPresentationAssets } from "../../api/presentation";
import { formatBytes } from "../../api/utils";
import { useUi, useUiLanguage } from "../../i18n";
import { requiredLocale, TransitionLink } from "../../navigation";
import { ArchivePage, EmptyState, PageHeader } from "../../shared/Page";
import { ArtworkGrid } from "../../shared/ui/ArtworkGrid";
import { Eyebrow } from "../../shared/ui/Typography";

export function PresentationAssetCatalogPage() {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const locale = requiredLocale(useParams().locale);
  const location = useLocation();
  const assets = use(getPresentationAssets(locale));
  const [searchParams, setSearchParams] = useSearchParams();
  const categories = [...new Set(assets.map((asset) => asset.category))];
  const category = categories.find((value) => value === searchParams.get("category")) ?? "";
  const formatParam = searchParams.get("format");
  const format = formatParam === "image" || formatParam === "video" ? formatParam : "";
  const referenceParam = searchParams.get("references");
  const referenceState =
    referenceParam === "referenced" || referenceParam === "orphaned" ? referenceParam : "";

  function setFilter(key: string, value: string): void {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  }

  const visible = assets.filter(
    (asset) =>
      (!category || asset.category === category) &&
      (!format || asset.format === format) &&
      (!referenceState || (asset.referenceCount === 0) === (referenceState === "orphaned")),
  );

  return (
    <ArchivePage description={t("presentation.description")} title={t("presentation.title")}>
      <PageHeader
        description={t("presentation.description")}
        eyebrow={t("presentation.eyebrow")}
        meta={<span>{t("presentation.assetCount", { count: visible.length })}</span>}
        title={t("presentation.title")}
      />
      <div className="my-8 grid gap-4 border-2 border-ink bg-surface p-4 sm:grid-cols-3">
        <label className="grid gap-2 text-xs font-extrabold uppercase">
          {t("presentation.category")}
          <select
            className="min-h-11 border-2 border-ink bg-white px-3"
            onChange={(event) => setFilter("category", event.currentTarget.value)}
            value={category}
          >
            <option value="">{t("presentation.all")}</option>
            {categories.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-2 text-xs font-extrabold uppercase">
          {t("presentation.format")}
          <select
            className="min-h-11 border-2 border-ink bg-white px-3"
            onChange={(event) => setFilter("format", event.currentTarget.value)}
            value={format}
          >
            <option value="">{t("presentation.all")}</option>
            <option value="image">{t("presentation.image")}</option>
            <option value="video">{t("presentation.video")}</option>
          </select>
        </label>
        <label className="grid gap-2 text-xs font-extrabold uppercase">
          {t("presentation.referenceState")}
          <select
            className="min-h-11 border-2 border-ink bg-white px-3"
            onChange={(event) => setFilter("references", event.currentTarget.value)}
            value={referenceState}
          >
            <option value="">{t("presentation.all")}</option>
            <option value="referenced">{t("presentation.referenced")}</option>
            <option value="orphaned">{t("presentation.orphaned")}</option>
          </select>
        </label>
      </div>
      {visible.length ? (
        <ArtworkGrid>
          {visible.map((asset) => (
            <article
              className="flex min-w-0 flex-col border-2 border-ink bg-surface"
              key={`${asset.category}:${asset.id}`}
            >
              <TransitionLink
                className="checkerboard grid aspect-video place-items-center overflow-hidden border-b-2 border-ink bg-black text-white no-underline"
                state={{ from: `${location.pathname}${location.search}` }}
                to={`/${locale}/assets/presentation/${asset.category}/${encodeURIComponent(asset.id)}`}
                transition="forward"
              >
                {asset.previewUrl ? (
                  <img alt="" className="size-full object-contain" src={asset.previewUrl} />
                ) : (
                  <span className="font-mono text-xs font-bold uppercase">{asset.format}</span>
                )}
              </TransitionLink>
              <div className="flex flex-1 flex-col p-5">
                <Eyebrow>{asset.category}</Eyebrow>
                <code className="mb-5 break-all text-sm font-extrabold">{asset.id}</code>
                <div className="mt-auto flex flex-wrap gap-3 text-xs text-muted">
                  {asset.width !== null && asset.height !== null ? (
                    <span>{`${asset.width} × ${asset.height}`}</span>
                  ) : asset.duration !== null ? (
                    <span>{`${asset.duration.toFixed(2)} s`}</span>
                  ) : null}
                  <span>{formatBytes(asset.size, language)}</span>
                  <span>{t("presentation.referenceCount", { count: asset.referenceCount })}</span>
                </div>
              </div>
            </article>
          ))}
        </ArtworkGrid>
      ) : (
        <EmptyState title={t("presentation.empty")}>{t("presentation.emptyHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
