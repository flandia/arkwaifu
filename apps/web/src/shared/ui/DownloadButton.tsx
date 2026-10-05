import { useEffect, useRef, useState, type ReactNode } from "react";
import { useUi } from "../../i18n";
import { downloadFile } from "../download";
import { ActionButton } from "./Action";

export function DownloadButton({ children, url }: { children: ReactNode; url: string }) {
  const { t } = useUi();
  const controllerRef = useRef<AbortController | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setPending(false);
    setFailed(false);
    return () => controllerRef.current?.abort();
  }, [url]);

  async function download(): Promise<void> {
    const controller = new AbortController();
    controllerRef.current = controller;
    setPending(true);
    setFailed(false);
    try {
      await downloadFile(url, controller.signal);
    } catch {
      if (!controller.signal.aborted) setFailed(true);
    } finally {
      if (!controller.signal.aborted) setPending(false);
    }
  }

  return (
    <div className="grid gap-3">
      <ActionButton aria-busy={pending || undefined} disabled={pending} onClick={download}>
        {pending ? t("common.downloading") : children}
      </ActionButton>
      {failed ? (
        <p className="m-0 text-sm leading-relaxed" role="alert">
          {t("common.downloadFailed")}
        </p>
      ) : null}
    </div>
  );
}
