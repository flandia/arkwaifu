/** Downloads cross-origin media through a browser-owned, same-origin Blob URL. */
export async function downloadFile(url: string, signal: AbortSignal): Promise<void> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`Download failed: ${response.status}`);
  const blob = await response.blob();
  signal.throwIfAborted();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  try {
    anchor.href = objectUrl;
    anchor.download = decodeURIComponent(new URL(url).pathname.split("/").at(-1) || "download");
    document.body.append(anchor);
    anchor.click();
  } finally {
    anchor.remove();
    // Let the browser start consuming the Blob before releasing its URL.
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }
}
