import { use } from "react";
import { useParams } from "react-router";
import { getArchiveStory } from "../../api/archives";
import { ApiError } from "../../api/client";
import { useUi } from "../../i18n";
import { requiredArchiveKind, requiredLocale } from "../../navigation";
import { OwnedStoryDetail } from "../hierarchy/StoryDetail";

export function ArchiveStoryPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const kind = requiredArchiveKind(params.kind);
  const groupID = params.groupID ?? "";
  const story = use(getArchiveStory(locale, kind, groupID, params.storyID ?? ""));
  if (
    story.parent.kind !== "archive" ||
    story.parent.archiveKind !== kind ||
    story.parent.groupID !== groupID
  ) {
    throw new ApiError(t("errors.wrongStoryParent"), 404);
  }
  const backTo = `/${locale}/archives/${kind}/${encodeURIComponent(groupID)}`;
  return <OwnedStoryDetail backTo={backTo} locale={locale} story={story} />;
}
