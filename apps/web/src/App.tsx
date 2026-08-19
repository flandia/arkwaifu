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
const NarrativeImageAssetPage = lazy(async () => ({
  default: (await import("./features/artwork/NarrativeImageAssetPage")).NarrativeImageAssetPage,
}));
const MaterialAssetDetailPage = lazy(async () => ({
  default: (await import("./features/artwork/MaterialAssetDetailPage")).MaterialAssetDetailPage,
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
const GalleryGroupPage = lazy(async () => ({
  default: (await import("./features/galleries/GalleryGroupPage")).GalleryGroupPage,
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
const NarrativeMediaAssetPage = lazy(async () => ({
  default: (await import("./features/media/NarrativeMediaAssetPage")).NarrativeMediaAssetPage,
}));
const ScoreIndexPage = lazy(async () => ({
  default: (await import("./features/scores/ScoreIndexPage")).ScoreIndexPage,
}));
const SectionPage = lazy(async () => ({
  default: (await import("./features/scores/SectionPage")).SectionPage,
}));
const ScoreStoryPage = lazy(async () => ({
  default: (await import("./features/scores/ScoreStoryPage")).ScoreStoryPage,
}));
const SearchPage = lazy(async () => ({
  default: (await import("./features/search")).SearchPage,
}));
const OrphanNarrativeAssetsPage = lazy(async () => ({
  default: (await import("./features/artwork/OrphanNarrativeAssetsPage")).OrphanNarrativeAssetsPage,
}));
const PresentationAssetCatalogPage = lazy(async () => ({
  default: (await import("./features/presentation/PresentationAssetCatalogPage"))
    .PresentationAssetCatalogPage,
}));
const PresentationAssetDetailPage = lazy(async () => ({
  default: (await import("./features/presentation/PresentationAssetDetailPage"))
    .PresentationAssetDetailPage,
}));

function NarrativeAssetPage() {
  const category = useParams()["asset-category"];
  return category === "audio" || category === "video" ? (
    <NarrativeMediaAssetPage />
  ) : (
    <NarrativeImageAssetPage />
  );
}

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
        <Route element={<MovementPage />} path="scores/:movement-id" />
        <Route element={<SectionPage />} path="scores/:movement-id/:section-id" />
        <Route element={<ScoreStoryPage />} path="scores/:movement-id/:section-id/:story-id" />
        <Route element={<ArchiveIndexPage />} path="archives" />
        <Route element={<ArchiveGroupsPage />} path="archives/:archive-category" />
        <Route element={<ArchiveGroupPage />} path="archives/:archive-category/:group-id" />
        <Route
          element={<ArchiveStoryPage />}
          path="archives/:archive-category/:group-id/:story-id"
        />
        <Route element={<GalleryIndexPage />} path="galleries" />
        <Route element={<GalleryDetailPage />} path="galleries/:gallery-id" />
        <Route
          element={<GalleryGroupPage />}
          path="galleries/:gallery-id/groups/:group-id/:reference-id"
        />
        <Route element={<GalleryGroupPage />} path="galleries/:gallery-id/groups/:group-id" />
        <Route element={<OrphanNarrativeAssetsPage />} path="orphans" />
        <Route element={<PresentationAssetCatalogPage />} path="assets/presentation" />
        <Route
          element={<PresentationAssetDetailPage />}
          path="assets/presentation/:asset-category/:asset-id"
        />
        <Route element={<NarrativeAssetPage />} path="assets/narrative/:asset-category/:asset-id" />
        <Route
          element={<MaterialAssetDetailPage />}
          path="assets/material/:asset-category/:asset-id"
        />
        <Route element={<AboutPage />} path="about" />
        <Route element={<NotFoundPage />} path="*" />
      </Route>
      <Route element={<NotFoundLayout />} path="*" />
    </Routes>
  );
}
