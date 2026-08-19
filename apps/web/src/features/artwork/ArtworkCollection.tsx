import { useState } from "react";
import type { NarrativeImageCategory, Locale } from "../../api/types";
import { useUi } from "../../i18n";
import { useCategoryLabel } from "../../navigation";
import { ActionButton } from "../../shared/ui/Action";
import { ArtworkGrid } from "../../shared/ui/ArtworkGrid";
import { SectionHeading } from "../../shared/ui/Typography";
import { ArtworkCard } from "./ArtworkCard";

const categoryOrder: NarrativeImageCategory[] = ["illustration", "background", "item", "character"];
const initialArtworkCount = 7;

export interface ArtworkCollectionItem {
  asset: { category: NarrativeImageCategory; id: string };
  isAnimeKV?: boolean;
  title?: string | null;
  subtitle?: string | null;
  names?: string[];
  previewUrl?: string;
}

function artworkTitle(artwork: ArtworkCollectionItem, category: string): string {
  return (
    artwork.title?.trim() ||
    artwork.names?.filter(Boolean).join(", ") ||
    `${category} ${artwork.asset.id}`
  );
}

function NarrativeImageCategorySection({
  category,
  eyebrow,
  from,
  items,
  language,
  locale,
  tone,
}: {
  category: NarrativeImageCategory;
  eyebrow?: string;
  from: string;
  items: ArtworkCollectionItem[];
  language: string;
  locale: Locale;
  tone: "light" | "dark";
}) {
  const { t } = useUi();
  const labelCategory = useCategoryLabel();
  const [expanded, setExpanded] = useState(false);
  const visibleItems = expanded ? items : items.slice(0, initialArtworkCount);

  return (
    <section className="scroll-mt-8" id={category}>
      <SectionHeading
        eyebrow={eyebrow ?? t("artwork.assetCategory")}
        meta={new Intl.NumberFormat().format(items.length)}
        title={labelCategory(category, true)}
        tone={tone}
      />
      {items.length ? (
        <ArtworkGrid>
          {visibleItems.map((artwork) => (
            <ArtworkCard
              badge={artwork.isAnimeKV ? t("artwork.animeKV") : undefined}
              category={artwork.asset.category}
              from={from}
              id={artwork.asset.id}
              key={`${artwork.asset.category}:${artwork.asset.id}`}
              language={language}
              locale={locale}
              subtitle={artwork.subtitle ?? undefined}
              thumbnailUrl={artwork.previewUrl ?? null}
              title={artworkTitle(artwork, labelCategory(artwork.asset.category))}
            />
          ))}
        </ArtworkGrid>
      ) : (
        <p
          className={
            tone === "dark" ? "m-0 leading-relaxed text-white/70" : "m-0 leading-relaxed text-muted"
          }
        >
          {t("artwork.noArtworkInCategory")}
        </p>
      )}
      {items.length > initialArtworkCount ? (
        <div className="mt-8 flex justify-center">
          <ActionButton
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
            variant="secondary"
          >
            {expanded ? t("artwork.showFewer") : t("artwork.showAll", { count: items.length })}
          </ActionButton>
        </div>
      ) : null}
    </section>
  );
}

export function ArtworkCollection({
  eyebrow,
  from,
  language,
  locale,
  artworks,
  tone = "light",
}: {
  eyebrow?: string;
  from: string;
  language: string;
  locale: Locale;
  artworks: ArtworkCollectionItem[];
  tone?: "light" | "dark";
}) {
  const byCategory = new Map<NarrativeImageCategory, ArtworkCollectionItem[]>();
  for (const artwork of artworks) {
    const values = byCategory.get(artwork.asset.category) ?? [];
    values.push(artwork);
    byCategory.set(artwork.asset.category, values);
  }

  return (
    <div className="mt-16 grid gap-24">
      {categoryOrder.map((category) => {
        const items = byCategory.get(category) ?? [];
        return (
          <NarrativeImageCategorySection
            category={category}
            eyebrow={eyebrow}
            from={from}
            items={items}
            key={`${from}:${category}`}
            language={language}
            locale={locale}
            tone={tone}
          />
        );
      })}
    </div>
  );
}
