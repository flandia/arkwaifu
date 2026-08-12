import { useState } from "react";
import type { ArtCategory, Locale } from "../../api";
import { useUi } from "../../i18n";
import { useCategoryLabel } from "../../navigation";
import { ActionButton, ArtworkGrid, SectionHeading } from "../../shared/ui";
import { ArtworkCard } from "./ArtworkCard";

const categoryOrder: ArtCategory[] = ["image", "background", "item", "character"];
const initialArtworkCount = 7;

export interface ArtworkCollectionItem {
  artID: string;
  category: ArtCategory;
  title?: string | null;
  subtitle?: string | null;
  names?: string[];
  thumbnailContentUrl: string | null;
}

function artworkTitle(artwork: ArtworkCollectionItem, category: string): string {
  return (
    artwork.title?.trim() ||
    artwork.names?.filter(Boolean).join(", ") ||
    `${category} ${artwork.artID}`
  );
}

function ArtworkCategorySection({
  category,
  eyebrow,
  from,
  items,
  language,
  locale,
}: {
  category: ArtCategory;
  eyebrow?: string;
  from: string;
  items: ArtworkCollectionItem[];
  language: string;
  locale: Locale;
}) {
  const { t } = useUi();
  const labelCategory = useCategoryLabel();
  const [expanded, setExpanded] = useState(false);
  const visibleItems = expanded ? items : items.slice(0, initialArtworkCount);

  return (
    <section className="scroll-mt-8" id={category}>
      <SectionHeading
        eyebrow={eyebrow ?? t("story.assetCategory")}
        meta={new Intl.NumberFormat().format(items.length)}
        title={labelCategory(category, true)}
      />
      {items.length ? (
        <ArtworkGrid>
          {visibleItems.map((artwork) => (
            <ArtworkCard
              category={artwork.category}
              from={from}
              id={artwork.artID}
              key={`${artwork.category}:${artwork.artID}`}
              language={language}
              locale={locale}
              subtitle={artwork.subtitle ?? undefined}
              thumbnailUrl={artwork.thumbnailContentUrl}
              title={artworkTitle(artwork, labelCategory(artwork.category))}
            />
          ))}
        </ArtworkGrid>
      ) : (
        <p className="m-0 leading-relaxed text-muted">{t("art.noArtworkInCategory")}</p>
      )}
      {items.length > initialArtworkCount ? (
        <div className="mt-8 flex justify-center">
          <ActionButton
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
            variant="secondary"
          >
            {expanded ? t("art.showFewer") : t("art.showAll", { count: items.length })}
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
}: {
  eyebrow?: string;
  from: string;
  language: string;
  locale: Locale;
  artworks: ArtworkCollectionItem[];
}) {
  const byCategory = new Map<ArtCategory, ArtworkCollectionItem[]>();
  for (const artwork of artworks) {
    const values = byCategory.get(artwork.category) ?? [];
    values.push(artwork);
    byCategory.set(artwork.category, values);
  }

  return (
    <div className="mt-16 grid gap-24">
      {categoryOrder.map((category) => {
        const items = byCategory.get(category) ?? [];
        return (
          <ArtworkCategorySection
            category={category}
            eyebrow={eyebrow}
            from={from}
            items={items}
            key={`${from}:${category}`}
            language={language}
            locale={locale}
          />
        );
      })}
    </div>
  );
}
