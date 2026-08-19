import type { CSSProperties } from "react";
import type { Locale, SectionSummary, MovementDivider } from "../../api/types";
import { useUi } from "../../i18n";
import { localeLanguageTag, TransitionLink } from "../../navigation";
import { Eyebrow } from "../../shared/ui/Typography";
import { ScoreBackdrop, ScoreImageAsset } from "../hierarchy/ScoreVisual";

function imageRatio(section: SectionSummary): CSSProperties {
  const image = section.keyVisual?.image;
  return image ? { aspectRatio: `${image.width} / ${image.height}` } : { aspectRatio: "4 / 3" };
}

export function MovementDividerCard({ divider }: { divider: MovementDivider }) {
  const { t } = useUi();
  const video = divider.video?.video;
  return (
    <li
      className="relative overflow-hidden bg-black text-white [contain-intrinsic-block-size:auto_31rem] [content-visibility:auto]"
      style={{ aspectRatio: video ? `${video.width} / ${video.height}` : "50 / 31" }}
    >
      <ScoreBackdrop image={null} video={divider.video} viewportGated />
      <span
        className="absolute inset-0 bg-gradient-to-tr from-black/90 via-black/20 to-transparent"
        aria-hidden="true"
      />
      <div className="absolute right-0 bottom-0 left-0 z-10 flex items-end gap-5 p-[clamp(1.25rem,4vw,3.5rem)]">
        <ScoreImageAsset
          alt=""
          asset={divider.icon}
          className="max-h-24 max-w-[min(38%,12rem)] object-contain object-left-bottom drop-shadow-xl"
        />
        <div>
          <Eyebrow className="text-white/70">{t("score.divider")}</Eyebrow>
          <h2 className="m-0 text-[clamp(1.5rem,4vw,4rem)] leading-none font-black tracking-tight uppercase">
            {divider.subName || t("score.untitledDivider")}
          </h2>
        </div>
      </div>
    </li>
  );
}

export function MainThemeSectionRow({
  locale,
  movementID,
  section,
}: {
  locale: Locale;
  movementID: string;
  section: SectionSummary;
}) {
  const { t } = useUi();
  const language = localeLanguageTag(locale);
  return (
    <li
      className="scroll-mt-8 [contain-intrinsic-block-size:auto_32rem] [content-visibility:auto]"
      id={`movement-section-${section.id}`}
    >
      <TransitionLink
        className="group relative grid min-h-[34rem] overflow-hidden bg-black text-white no-underline min-[68rem]:min-h-0 min-[68rem]:aspect-[1660/936]"
        to={`/${locale}/scores/${encodeURIComponent(movementID)}/${encodeURIComponent(section.id)}`}
        transition="forward"
      >
        <ScoreImageAsset
          alt=""
          asset={section.retroBackground ?? section.background}
          className="absolute inset-0 size-full object-cover object-center brightness-75 transition-[filter,transform] duration-500 group-hover:scale-[1.01] group-hover:brightness-100 motion-reduce:transform-none"
        />
        <span
          className="absolute inset-0 bg-gradient-to-t from-black via-black/30 to-transparent min-[68rem]:bg-gradient-to-l min-[68rem]:from-black/95 min-[68rem]:via-black/45 min-[68rem]:to-transparent"
          aria-hidden="true"
        />
        <ScoreImageAsset
          alt=""
          asset={section.decoration}
          className="absolute top-[clamp(1.25rem,3vw,2.5rem)] right-[clamp(1.25rem,3vw,2.5rem)] z-10 max-h-20 max-w-20 object-contain drop-shadow-xl"
        />
        <div className="relative z-10 mt-auto flex min-w-0 max-w-3xl flex-col items-end justify-end p-[clamp(1.5rem,4vw,3.5rem)] text-right min-[68rem]:ml-auto min-[68rem]:w-[52%]">
          <ScoreImageAsset
            alt=""
            asset={section.titleImage}
            className="mb-5 max-h-28 max-w-full object-contain object-right drop-shadow-xl"
          />
          <Eyebrow className="text-white/65">{t(`score.sectionTypes.${section.type}`)}</Eyebrow>
          <h3
            className="mb-3 break-words text-[clamp(1.8rem,3.5vw,3.8rem)] leading-[0.95] font-black"
            lang={language}
          >
            {section.name || t("score.untitledSection")}
          </h3>
          <p className="mb-5 line-clamp-4 leading-relaxed text-white/70" lang={language}>
            {section.description}
          </p>
          <div className="flex flex-wrap justify-end gap-4 font-mono text-xs text-white/55">
            <code translate="no">{section.id}</code>
            <span>{t("story.count", { count: section.storyCount })}</span>
          </div>
        </div>
      </TransitionLink>
    </li>
  );
}

export function SectionCard({
  locale,
  movementID,
  section,
}: {
  locale: Locale;
  movementID: string;
  section: SectionSummary;
}) {
  const { t } = useUi();
  const language = localeLanguageTag(locale);
  return (
    <li className="min-w-0 [contain-intrinsic-block-size:auto_34rem] [content-visibility:auto]">
      <TransitionLink
        className="group relative grid w-full overflow-hidden bg-transparent text-white no-underline @container/card"
        style={imageRatio(section)}
        to={`/${locale}/scores/${encodeURIComponent(movementID)}/${encodeURIComponent(section.id)}`}
        transition="forward"
      >
        <ScoreImageAsset
          alt=""
          asset={section.keyVisual}
          className="absolute inset-0 size-full object-contain brightness-70 transition-[filter,transform] duration-500 group-hover:scale-[1.02] group-hover:brightness-100 motion-reduce:transform-none"
        />
        <div className="relative z-10 mt-auto flex min-h-full flex-col justify-end p-6">
          <ScoreImageAsset
            alt=""
            asset={section.titleImage}
            className="mb-5 max-h-24 max-w-full object-contain object-left"
          />
          <Eyebrow className="text-white/60">{t(`score.sectionTypes.${section.type}`)}</Eyebrow>
          <h3
            className="mb-3 break-words text-[clamp(1.7rem,3vw,3rem)] leading-none font-black"
            lang={language}
          >
            {section.name || t("score.untitledSection")}
          </h3>
          <p
            className="mb-6 hidden line-clamp-3 leading-relaxed text-white/65 @min-[24rem]/card:block"
            lang={language}
          >
            {section.description}
          </p>
          <div className="flex flex-wrap justify-between gap-3 font-mono text-xs text-white/50">
            <code translate="no">{section.id}</code>
            <span>{t("story.count", { count: section.storyCount })}</span>
          </div>
        </div>
      </TransitionLink>
    </li>
  );
}
