import { use } from "react";
import { useParams } from "react-router";
import { getArchiveStory } from "../../api/archives";
import { ApiError } from "../../api/client";
import { useUi } from "../../i18n";
import { requiredArchiveCategory, requiredLocale } from "../../navigation";
import { OwnedStoryDetail } from "../hierarchy/StoryDetail";

export function ArchiveStoryPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const category = requiredArchiveCategory(params["archive-category"]);
  const groupID = params["group-id"] ?? "";
  const story = use(getArchiveStory(locale, category, groupID, params["story-id"] ?? ""));
  if (
    story.parent.kind !== "archive" ||
    story.parent.archiveCategory !== category ||
    story.parent.groupID !== groupID
  ) {
    throw new ApiError(t("errors.wrongStoryParent"), 404);
  }
  const backTo = `/${locale}/archives/${category}/${encodeURIComponent(groupID)}`;
  return <OwnedStoryDetail backTo={backTo} locale={locale} story={story} />;
}
