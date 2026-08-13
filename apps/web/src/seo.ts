const siteOrigin = "https://arkwaifu.cc";

export function isSearchMirror(hostname: string): boolean {
  return hostname === "cn.arkwaifu.cc";
}

export function canonicalUrl(path: string): string {
  const pathname = (path.split(/[?#]/, 1)[0] || "/").replace(/^\/*/, "/");
  const normalizedPath = pathname === "/" ? pathname : pathname.replace(/\/+$/, "");
  return `${siteOrigin}${normalizedPath || "/"}`;
}

function upsertMeta(attribute: "name" | "property", key: string, content: string): void {
  let element = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute(attribute, key);
    document.head.append(element);
  }
  element.content = content;
}

function optionalMeta(attribute: "name" | "property", key: string, content?: string): void {
  if (content) upsertMeta(attribute, key, content);
  else document.head.querySelector(`meta[${attribute}="${key}"]`)?.remove();
}

interface PageMetadata {
  canonicalUrl: string;
  description: string;
  image?: string;
  noIndex: boolean;
  title: string;
}

export function applyPageMetadata(metadata: PageMetadata): void {
  const blockIndex = metadata.noIndex || isSearchMirror(window.location.hostname);
  document.title = metadata.title;

  if (metadata.noIndex) {
    document.head.querySelector('link[rel="canonical"]')?.remove();
  } else {
    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.rel = "canonical";
      document.head.append(canonical);
    }
    canonical.href = metadata.canonicalUrl;
  }

  upsertMeta("name", "description", metadata.description);
  optionalMeta("name", "robots", blockIndex ? "noindex,follow" : undefined);
  upsertMeta("property", "og:site_name", "Arkwaifu");
  upsertMeta("property", "og:type", "website");
  upsertMeta("property", "og:title", metadata.title);
  upsertMeta("property", "og:description", metadata.description);
  optionalMeta("property", "og:url", metadata.noIndex ? undefined : metadata.canonicalUrl);
  optionalMeta("property", "og:image", metadata.image);
  upsertMeta("name", "twitter:card", metadata.image ? "summary_large_image" : "summary");
  upsertMeta("name", "twitter:title", metadata.title);
  upsertMeta("name", "twitter:description", metadata.description);
  optionalMeta("name", "twitter:image", metadata.image);
}
