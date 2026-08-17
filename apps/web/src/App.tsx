import { lazy, Suspense, useEffect, useRef, type ErrorInfo } from "react";
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
import { ApiError, clearApiCache } from "./api/client";
import type { Locale } from "./api/types";
import { AppShell } from "./app/AppShell";
import { useUi } from "./i18n";
import { isLocale, LoadingPage } from "./navigation";
import { ArchivePage } from "./shared/Page";
import { ActionButton, ActionLink } from "./shared/ui/Action";
import { Eyebrow } from "./shared/ui/Typography";

const AboutPage = lazy(async () => ({ default: (await import("./features/about")).AboutPage }));
const ArtDetailPage = lazy(async () => ({
  default: (await import("./features/artwork/ArtDetailPage")).ArtDetailPage,
}));
const ArchiveGroupPage = lazy(async () => ({
  default: (await import("./features/archives/ArchiveGroupPage")).ArchiveGroupPage,
}));
const ArchiveGroupsPage = lazy(async () => ({
  default: (await import("./features/archives/ArchiveGroupsPage")).ArchiveGroupsPage,
}));
const ArchiveIndexPage = lazy(async () => ({
  default: (await import("./features/archives/ArchiveIndexPage")).ArchiveIndexPage,
}));
const ArchiveStoryPage = lazy(async () => ({
  default: (await import("./features/archives/ArchiveStoryPage")).ArchiveStoryPage,
}));
const GalleryDetailPage = lazy(async () => ({
  default: (await import("./features/galleries/GalleryDetailPage")).GalleryDetailPage,
}));
const GalleryDisplayPage = lazy(async () => ({
  default: (await import("./features/galleries/GalleryDisplayPage")).GalleryDisplayPage,
}));
const GalleryIndexPage = lazy(async () => ({
  default: (await import("./features/galleries/GalleryIndexPage")).GalleryIndexPage,
}));
const HomePage = lazy(async () => ({ default: (await import("./features/home")).HomePage }));
const NotFoundPage = lazy(async () => ({
  default: (await import("./features/not-found")).NotFoundPage,
}));
const MovementPage = lazy(async () => ({
  default: (await import("./features/scores/MovementPage")).MovementPage,
}));
const MediaDetailPage = lazy(async () => ({
  default: (await import("./features/media/MediaDetailPage")).MediaDetailPage,
}));
const ScoreIndexPage = lazy(async () => ({
  default: (await import("./features/scores/ScoreIndexPage")).ScoreIndexPage,
}));
const ScoreSectionPage = lazy(async () => ({
  default: (await import("./features/scores/ScoreSectionPage")).ScoreSectionPage,
}));
const ScoreStoryPage = lazy(async () => ({
  default: (await import("./features/scores/ScoreStoryPage")).ScoreStoryPage,
}));
const SearchPage = lazy(async () => ({
  default: (await import("./features/search")).SearchPage,
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
  if (!isLocale(locale)) return <NotFoundLayout />;

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

function NotFoundLayout() {
  return (
    <AppShell>
      <Suspense fallback={<LoadingPage />}>
        <NotFoundPage />
      </Suspense>
    </AppShell>
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
    <ArchivePage description={message} noIndex title={title}>
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
    </ArchivePage>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Navigate replace to={`/${preferredLocale()}`} />} path="/" />
      <Route element={<LocalizedLayout />} path="/:locale">
        <Route element={<HomePage />} index />
        <Route element={<SearchPage />} path="search" />
        <Route element={<ScoreIndexPage />} path="scores" />
        <Route element={<MovementPage />} path="scores/:movementID" />
        <Route element={<ScoreSectionPage />} path="scores/:movementID/:sectionID" />
        <Route element={<ScoreStoryPage />} path="scores/:movementID/:sectionID/:storyID" />
        <Route element={<ArchiveIndexPage />} path="archives" />
        <Route element={<ArchiveGroupsPage />} path="archives/:kind" />
        <Route element={<ArchiveGroupPage />} path="archives/:kind/:groupID" />
        <Route element={<ArchiveStoryPage />} path="archives/:kind/:groupID/:storyID" />
        <Route element={<GalleryIndexPage />} path="galleries" />
        <Route element={<GalleryDetailPage />} path="galleries/:galleryID" />
        <Route
          element={<GalleryDisplayPage />}
          path="galleries/:galleryID/displays/:displayID/:cgID"
        />
        <Route element={<GalleryDisplayPage />} path="galleries/:galleryID/displays/:displayID" />
        <Route element={<UnreferencedArtPage />} path="unreferenced" />
        <Route element={<ArtDetailPage />} path="art/:category/:artID" />
        <Route element={<MediaDetailPage />} path="media/:kind/:mediaID" />
        <Route element={<AboutPage />} path="about" />
        <Route element={<NotFoundPage />} path="*" />
      </Route>
      <Route element={<NotFoundLayout />} path="*" />
    </Routes>
  );
}
