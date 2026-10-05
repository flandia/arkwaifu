import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useUi } from "../i18n";

const BackgroundMotionContext = createContext({
  paused: false,
  reducedMotion: false,
  toggle: () => {},
});

export function BackgroundMotionProvider({ children }: { children: ReactNode }) {
  const [paused, setPaused] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return (
    <BackgroundMotionContext
      value={{
        paused: paused || reducedMotion,
        reducedMotion,
        toggle: () => setPaused((value) => !value),
      }}
    >
      {children}
    </BackgroundMotionContext>
  );
}

export function useBackgroundMotion() {
  return useContext(BackgroundMotionContext);
}

export function BackgroundMotionControl() {
  const { t } = useUi();
  const { paused, reducedMotion, toggle } = useBackgroundMotion();
  return (
    <button
      className="min-h-11 border-2 border-ink bg-surface px-3 py-2 text-xs font-bold text-ink hover:bg-paper disabled:opacity-60"
      disabled={reducedMotion}
      onClick={toggle}
      type="button"
    >
      {reducedMotion
        ? t("utility.reducedMotion")
        : paused
          ? t("score.resumeAnimation")
          : t("score.pauseAnimation")}
    </button>
  );
}
