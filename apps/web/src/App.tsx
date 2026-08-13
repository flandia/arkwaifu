import { lazy, Suspense, use, useEffect, useRef, type ErrorInfo } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";
import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigationType,
  useParams,
} from "react-router";
import {
  ApiError,
  clearApiCache,
  getLegacyArtCategories,
  getStory,
  getStoryGroups,
  type Locale,
} from "./api";
import { AppShell } from "./app/AppShell";
import { useUi } from "./i18n";
import {
  isLocale,
  LoadingPage,
  PageTransition,
  sectionForType,
  useCategoryLabel,
} from "./navigation";
import { ActionButton, ActionLink, Eyebrow } from "./shared/ui";

const AboutPage = lazy(async () => ({ default: (await import("./features/about")).AboutPage }));
const ArtDetailPage = lazy(async () => ({
  default: (await import("./features/artwork/ArtDetailPage")).ArtDetailPage,
}));
const GalleriesPage = lazy(async () => ({
  default: (await import("./features/galleries")).GalleriesPage,
}));
const GalleryDetailPage = lazy(async () => ({
  default: (await import("./features/galleries")).GalleryDetailPage,
}));
const HomePage = lazy(async () => ({ default: (await import("./features/home")).HomePage }));
const NotFoundPage = lazy(async () => ({
  default: (await import("./features/not-found")).NotFoundPage,
}));
const StoryDetailPage = lazy(async () => ({
  default: (await import("./features/stories/StoryDetailPage")).StoryDetailPage,
}));
const StoryGroupPage = lazy(async () => ({
  default: (await import("./features/stories/StoryGroupPage")).StoryGroupPage,
}));
const StoryIndexPage = lazy(async () => ({
  default: (await import("./features/stories/StoryIndexPage")).StoryIndexPage,
}));
const UnreferencedArtPage = lazy(async () => ({
  default: (await import("./features/artwork/UnreferencedArtPage")).UnreferencedArtPage,
}));

function preferredLocale(): Locale {
  try {
    const saved = localStorage.getItem("arkwaifu-locale");
    if (isLocale(saved ?? undefined)) return saved as Locale;
  } catch {
    // Browser preference is the fallback when storage is unavailable.
  }

  return "CN";
}

function ScrollManager() {
  const { pathname } = useLocation();
  const navigationType = useNavigationType();
  const previousPathname = useRef(pathname);
  useEffect(() => {
    const pathChanged = previousPathname.current !== pathname;
    previousPathname.current = pathname;
    if (!pathChanged || navigationType === "POP") return;
    document.querySelector<HTMLElement>("#main-content")?.focus({ preventScroll: true });
    window.scrollTo({ left: 0, top: 0, behavior: "auto" });
  }, [navigationType, pathname]);
  return null;
}

function LocalizedLayout() {
  const { locale } = useParams();
  const location = useLocation();
  if (!isLocale(locale)) return <Navigate replace to={`/${preferredLocale()}`} />;

  return (
    <AppShell>
      <ScrollManager />
      <ErrorBoundary
        FallbackComponent={RouteErrorFallback}
        onError={logRouteError}
        resetKeys={[location.pathname]}
      >
        <Suspense fallback={<LoadingPage />}>
          <Outlet />
        </Suspense>
      </ErrorBoundary>
    </AppShell>
  );
}

function LegacyStaticRedirect({ suffix }: { suffix: string }) {
  return <Navigate replace to={`/${preferredLocale()}${suffix}`} />;
}

function LegacyParamRedirect({ kind }: { kind: "group" | "story" | "art" }) {
  const params = useParams();
  const value = params.id ?? "";
  return (
    <Navigate replace to={`/${preferredLocale()}/legacy/${kind}/${encodeURIComponent(value)}`} />
  );
}

function LegacyGalleryRedirect() {
  const galleryID = useParams().id ?? "";
  return (
    <Navigate replace to={`/${preferredLocale()}/galleries/${encodeURIComponent(galleryID)}`} />
  );
}

function LegacyUnclassifiedRedirect() {
  const locale = useParams().locale as Locale;
  return <Navigate replace to={`/${locale}/unreferenced`} />;
}

function LegacyGroupRedirect() {
  const { t } = useUi();
  const locale = useParams().locale as Locale;
  const groupID = useParams().id ?? "";
  const group = use(getStoryGroups(locale)).find((value) => value.id === groupID);
  if (!group) throw new ApiError(t("errors.missingStoryGroup"), 404);
  return (
    <Navigate
      replace
      to={`/${locale}/stories/${sectionForType(group.type)}/${encodeURIComponent(group.id)}`}
    />
  );
}

function LegacyStoryRedirect() {
  const { t } = useUi();
  const params = useParams();
  const locale = params.locale as Locale;
  const storyID = params.id ?? "";
  const storyRequest = getStory(locale, storyID);
  const groupsRequest = getStoryGroups(locale);
  const story = use(storyRequest);
  const group = use(groupsRequest).find((value) => value.id === story.groupID);
  if (!group) throw new ApiError(t("errors.missingStoryGroup"), 404);
  return (
    <Navigate
      replace
      to={`/${locale}/stories/${sectionForType(group.type)}/${encodeURIComponent(group.id)}/${encodeURIComponent(story.id)}`}
    />
  );
}

function LegacyArtRedirect() {
  const { t } = useUi();
  const labelCategory = useCategoryLabel();
  const params = useParams();
  const locale = params.locale as Locale;
  const artID = params.id ?? "";
  const categories = use(getLegacyArtCategories(artID));
  if (!categories.length) throw new ApiError(t("errors.missingArtwork"), 404);
  if (categories.length === 1) {
    return <Navigate replace to={`/${locale}/art/${categories[0]}/${encodeURIComponent(artID)}`} />;
  }
  return (
    <PageTransition>
      <section className="relative min-h-[60vh] pt-[clamp(3rem,8vw,7rem)]">
        <Eyebrow>{t("errors.legacyArtwork")}</Eyebrow>
        <h1 className="mb-7 max-w-[14ch] font-display text-[clamp(3.4rem,8vw,7.5rem)] leading-[0.88] font-black tracking-tight uppercase">
          {t("errors.chooseCategory")}
        </h1>
        <p className="mb-8 max-w-2xl text-lg leading-relaxed text-muted">
          {t("errors.ambiguousLegacyArt")}
        </p>
        <div className="flex flex-wrap gap-4">
          {categories.map((category) => (
            <ActionLink
              variant="secondary"
              key={category}
              to={`/${locale}/art/${category}/${encodeURIComponent(artID)}`}
              transition="forward"
            >
              {labelCategory(category)}
            </ActionLink>
          ))}
        </div>
      </section>
    </PageTransition>
  );
}

function logRouteError(error: unknown, info: ErrorInfo): void {
  if (!(error instanceof ApiError && error.status === 404)) {
    console.error("Archive route failed", error, info.componentStack);
  }
}

function RouteErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  const { t } = useUi();
  const { locale } = useParams();
  const overviewLocale = isLocale(locale) ? locale : preferredLocale();
  const notFound = error instanceof ApiError && error.status === 404;
  const title = notFound ? t("errors.notFound") : t("errors.unavailable");
  const message = notFound ? t("errors.notFoundMessage") : t("errors.unavailableMessage");

  return (
    <PageTransition>
      <section
        className="relative min-h-[60vh] overflow-hidden pt-[clamp(3rem,8vw,7rem)]"
        role="alert"
      >
        <p
          className="absolute top-0 right-0 -z-10 m-0 font-display text-[clamp(10rem,30vw,30rem)] leading-[0.8] text-brand-soft"
          aria-hidden="true"
        >
          {notFound ? "404" : "503"}
        </p>
        <Eyebrow>{t("errors.routeEyebrow")}</Eyebrow>
        <h1 className="mb-7 max-w-[14ch] font-display text-[clamp(3.4rem,8vw,7.5rem)] leading-[0.88] font-black tracking-tight uppercase">
          {title}
        </h1>
        <p className="mb-8 max-w-2xl text-lg leading-relaxed text-muted">{message}</p>
        <div className="flex flex-wrap gap-4">
          <ActionButton
            onClick={() => {
              clearApiCache();
              window.location.reload();
            }}
          >
            {t("errors.tryAgain")}
          </ActionButton>
          <ActionLink
            variant="secondary"
            onClick={resetErrorBoundary}
            to={`/${overviewLocale}`}
            transition="back"
          >
            {t("errors.returnOverview")}
          </ActionLink>
        </div>
      </section>
    </PageTransition>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Navigate replace to={`/${preferredLocale()}`} />} path="/" />
      <Route element={<LegacyStaticRedirect suffix="/about" />} path="/about" />
      <Route element={<LegacyStaticRedirect suffix="/galleries" />} path="/galleries" />
      <Route element={<LegacyGalleryRedirect />} path="/galleries/:id" />
      <Route element={<LegacyStaticRedirect suffix="/stories/main" />} path="/story/main-stories" />
      <Route
        element={<LegacyStaticRedirect suffix="/stories/events" />}
        path="/story/major-events"
      />
      <Route
        element={<LegacyStaticRedirect suffix="/stories/vignettes" />}
        path="/story/minor-events"
      />
      <Route element={<LegacyStaticRedirect suffix="/stories/records" />} path="/story/others" />
      <Route element={<LegacyParamRedirect kind="group" />} path="/story/groups/:id" />
      <Route element={<LegacyParamRedirect kind="story" />} path="/story/stories/:id" />
      <Route element={<LegacyParamRedirect kind="art" />} path="/arts/:id" />
      <Route element={<LocalizedLayout />} path="/:locale">
        <Route element={<HomePage />} index />
        <Route element={<StoryIndexPage />} path="stories/:section" />
        <Route element={<StoryGroupPage />} path="stories/:section/:groupID" />
        <Route element={<StoryDetailPage />} path="stories/:section/:groupID/:storyID" />
        <Route element={<GalleriesPage />} path="galleries" />
        <Route element={<GalleryDetailPage />} path="galleries/:galleryID" />
        <Route element={<UnreferencedArtPage />} path="unreferenced" />
        <Route element={<LegacyUnclassifiedRedirect />} path="unclassified" />
        <Route element={<ArtDetailPage />} path="art/:category/:artID" />
        <Route element={<AboutPage />} path="about" />
        <Route element={<LegacyGroupRedirect />} path="legacy/group/:id" />
        <Route element={<LegacyStoryRedirect />} path="legacy/story/:id" />
        <Route element={<LegacyArtRedirect />} path="legacy/art/:id" />
        <Route element={<NotFoundPage />} path="*" />
      </Route>
      <Route element={<Navigate replace to={`/${preferredLocale()}`} />} path="*" />
    </Routes>
  );
}
