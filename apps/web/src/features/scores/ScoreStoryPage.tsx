import { use } from "react";
import { useParams } from "react-router";
import { ApiError } from "../../api/client";
import { getScoreStory } from "../../api/scores";
import { useUi } from "../../i18n";
import { requiredLocale } from "../../navigation";
import { OwnedStoryDetail } from "../hierarchy/StoryDetail";

export function ScoreStoryPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const movementID = params["movement-id"] ?? "";
  const sectionID = params["section-id"] ?? "";
  const story = use(getScoreStory(locale, movementID, sectionID, params["story-id"] ?? ""));
  if (
    story.parent.kind !== "score" ||
    story.parent.movementID !== movementID ||
    story.parent.sectionID !== sectionID
  ) {
    throw new ApiError(t("errors.wrongStoryParent"), 404);
  }
  const backTo = `/${locale}/scores/${encodeURIComponent(movementID)}/${encodeURIComponent(sectionID)}`;
  return <OwnedStoryDetail backTo={backTo} locale={locale} story={story} />;
}
