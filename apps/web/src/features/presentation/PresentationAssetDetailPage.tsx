import { use } from "react";
import { useLocation, useParams } from "react-router";
import { getPresentationAsset } from "../../api/presentation";
import { formatBytes } from "../../api/utils";
import { useUi, useUiLanguage } from "../../i18n";
import {
  requiredLocale,
  requiredPresentationAssetCategory,
  TransitionLink,
} from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ActionLink } from "../../shared/ui/Action";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";

export function PresentationAssetDetailPage() {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const category = requiredPresentationAssetCategory(params["asset-category"]);
  const asset = use(getPresentationAsset(locale, category, params["asset-id"] ?? ""));
  const location = useLocation();
  const from = typeof location.state?.from === "string" ? location.state.from : undefined;
  const backTo = from?.startsWith(`/${locale}/`) ? from : `/${locale}/assets/presentation`;

  return (
    <ArchivePage description={`${asset.category} · ${asset.id}`} title={asset.id}>
      <BackLink to={backTo}>{t("presentation.back")}</BackLink>
      <PageHeader
        eyebrow={t("presentation.record")}
        meta={
          <>
            <span>{asset.mime}</span>
            <span>{formatBytes(asset.size, language)}</span>
          </>
        }
        title={asset.id}
      />
      <div className="mt-12 grid items-start gap-8 min-[56rem]:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]">
        <figure className="checkerboard m-0 grid min-h-72 place-items-center overflow-hidden border-[3px] border-ink bg-black">
          {asset.format === "image" ? (
            <img alt={asset.id} className="max-h-[75vh] w-full object-contain" src={asset.url} />
          ) : (
            // oxlint-disable-next-line jsx-a11y/media-has-caption
            <video className="max-h-[75vh] w-full" controls preload="metadata">
              <source src={asset.url} type={asset.mime} />
            </video>
          )}
        </figure>
        <aside className="border-2 border-ink bg-surface p-6">
          <Eyebrow>{t("presentation.identity")}</Eyebrow>
          <code className="mb-8 block break-all">
            presentation/{asset.category}/{asset.id}
          </code>
          <dl className="mb-8 border-t-2 border-ink">
            {[
              [t("presentation.format"), asset.mime],
              [t("artwork.fileSize"), formatBytes(asset.size, language)],
              asset.width && asset.height
                ? [t("artwork.dimensions"), `${asset.width} × ${asset.height}`]
                : null,
              asset.duration ? [t("mediaAsset.duration"), `${asset.duration.toFixed(2)} s`] : null,
            ]
              .filter((row): row is string[] => row !== null)
              .map(([term, value]) => (
                <div className="grid grid-cols-2 gap-4 border-b border-line py-4" key={term}>
                  <dt className="text-xs font-extrabold uppercase text-muted">{term}</dt>
                  <dd className="m-0 text-right text-xs">{value}</dd>
                </div>
              ))}
          </dl>
          <ActionLink adornment="external" target="_blank" to={asset.url}>
            {t("artwork.openOriginal")}
          </ActionLink>
        </aside>
      </div>
      <section className="mt-[clamp(4rem,9vw,8rem)]">
        <SectionHeading
          eyebrow={t("artwork.reverseReferences")}
          meta={new Intl.NumberFormat(language).format(asset.reverseReferences.length)}
          title={t("presentation.references")}
        />
        <div className="grid gap-4 md:grid-cols-2">
          {asset.reverseReferences.map((reference) => {
            const target =
              reference.ownerType === "section"
                ? `/${locale}/scores/${encodeURIComponent(reference.movementID)}/${encodeURIComponent(reference.ownerID)}`
                : `/${locale}/scores/${encodeURIComponent(reference.movementID)}`;
            return (
              <article
                className="border-2 border-ink bg-surface p-5"
                key={`${reference.ownerType}:${reference.ownerID}:${reference.role}`}
              >
                <Eyebrow>
                  {reference.ownerType} · {reference.role}
                </Eyebrow>
                <TransitionLink className="text-xl font-black" to={target} transition="forward">
                  {reference.name || reference.ownerID}
                </TransitionLink>
              </article>
            );
          })}
        </div>
      </section>
    </ArchivePage>
  );
}
