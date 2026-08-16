import { afterEach, describe, expect, it, mock, spyOn } from "bun:test";
import {
  getArchiveGroup,
  getArchiveGroups,
  getArchiveKinds,
  getArchiveStory,
} from "./api/archives";
import { getArt, getArtContext, getArtWithSources } from "./api/artwork";
import { ApiError, clearApiCache, resolveApiBaseUrl } from "./api/client";
import { getGalleries, getGallery } from "./api/galleries";
import { getSearchResults } from "./api/search";
import { getMovement, getMovements, getScoreSection, getScoreStory } from "./api/scores";
import type {
  ArchiveGroupDetail,
  ArchiveGroupSummary,
  ArchiveKindSummary,
  ArtContext,
  ArtDetail,
  GalleryDetail,
  GallerySummary,
  MovementDetail,
  MovementSummary,
  ScoreSectionDetail,
  StoryArtReference,
  StoryDetail,
  StorySummary,
} from "./api/types";
import { getUnreferencedArts } from "./api/unreferenced";
import { artTransitionName, formatBytes, uniqueStoryArtReferences } from "./api/utils";

const configuredApiBaseUrl = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

function apiUrl(path: string): string {
  return `${configuredApiBaseUrl}${path}`;
}

const reference: StoryArtReference = {
  artID: "char_220_grani#5$1",
  kind: "character",
  category: "character",
  title: null,
  subtitle: null,
  names: ["Grani"],
  thumbnailContentUrl:
    "https://objects.example/ART/art-v1/thumbnail/character/char_220_grani%25235%25241.webp",
};

const artResponse: ArtDetail = {
  id: reference.artID,
  category: reference.category,
  thumbnailContentUrl:
    "https://objects.example/ART/art-v1/thumbnail/character/char_220_grani%25235%25241.webp",
  image: {
    byteSize: 1536,
    width: 100,
    height: 200,
    contentUrl: "https://objects.example/art.png",
  },
  sourceArts: [],
};

const scoreParent = {
  kind: "score" as const,
  movementID: "main",
  movementName: "For Tomorrow",
  sectionID: "main_17",
  sectionName: "Critical Phase Transition",
};

const storySummary: StorySummary = {
  id: "main_17-1",
  tag: "before",
  tagText: "Before Operation",
  code: "17-1",
  name: "Seeds",
  info: "A story summary.",
  previewArtReferences: [reference],
  representativeArtReference: reference,
};

const storyDetail: StoryDetail = {
  id: storySummary.id,
  tag: storySummary.tag,
  tagText: storySummary.tagText,
  code: storySummary.code,
  name: storySummary.name,
  info: "A story detail.",
  parent: scoreParent,
  artReferences: [reference],
};

const galleryDetail: GalleryDetail = {
  id: "main_17",
  name: "Critical Phase Transition",
  description: "A gallery.",
  parent: scoreParent,
  displays: [
    {
      id: "sacrifice-torch",
      position: 0,
      name: "Sacrifice Torch",
      description: "Four sibling artworks.",
      relatedStoryID: storySummary.id,
      relatedStageID: null,
      artworks: [
        {
          position: 0,
          cgID: "cg_001",
          artID: "cg_001_a/cg_001_b",
          category: "image",
          thumbnailContentUrl: "https://objects.example/cg.webp",
        },
      ],
    },
  ],
};

const sectionDetail: ScoreSectionDetail = {
  id: scoreParent.sectionID,
  name: scoreParent.sectionName,
  description: "A section.",
  type: "main_theme",
  position: 1,
  sortByYear: 2026,
  sortWithinYear: 1,
  keyVisual: null,
  titleImage: null,
  background: null,
  decoration: null,
  retroBackground: null,
  storyCount: 1,
  activeBackgroundVideo: null,
  stories: [storySummary],
  artReferences: [reference],
  gallery: galleryDetail,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  clearApiCache();
  mock.restore();
});

describe("archive helpers", () => {
  it("defaults API requests to production and normalizes configured overrides", () => {
    expect(resolveApiBaseUrl(undefined)).toBe("https://api.arkwaifu.cc");
    expect(resolveApiBaseUrl(undefined, "cn.arkwaifu.cc")).toBe("https://api.cn.arkwaifu.cc");
    expect(resolveApiBaseUrl(" https://preview.example.test/root/// ", "cn.arkwaifu.cc")).toBe(
      "https://preview.example.test/root",
    );
  });

  it("deduplicates qualified art identities while preserving first occurrence", () => {
    const sameIDOtherCategory = { ...reference, category: "image" as const };
    expect(uniqueStoryArtReferences([reference, reference, sameIDOtherCategory])).toEqual([
      reference,
      sameIDOtherCategory,
    ]);
  });

  it("creates stable CSS-safe transition names", () => {
    expect(artTransitionName("character", reference.artID)).toMatch(/^art-[a-z0-9]+$/);
    expect(artTransitionName("character", reference.artID)).toBe(
      artTransitionName("character", reference.artID),
    );
    expect(artTransitionName("image", reference.artID)).not.toBe(
      artTransitionName("character", reference.artID),
    );
  });

  it("formats binary file sizes with localized numbers", () => {
    expect(formatBytes(512)).toBe("512\u00a0B");
    expect(formatBytes(1536)).toBe("1.5\u00a0KiB");
    expect(formatBytes(2 * 1024 * 1024)).toBe("2\u00a0MiB");
  });
});

describe("archive API client", () => {
  it("encodes art IDs and deduplicates in-flight requests", async () => {
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(artResponse));

    const first = getArt("character", reference.artID);
    const second = getArt("character", reference.artID);

    expect(first).toBe(second);
    expect(await first).toEqual(artResponse);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[0]).toBe(apiUrl("/api/arts/character/char_220_grani%235%241"));
  });

  it("retains failed requests until an explicit retry clears the cache", async () => {
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ error: "service_unavailable" }, 503))
      .mockResolvedValueOnce(jsonResponse(artResponse));

    const error = await getArt("character", reference.artID).catch((reason: unknown) => reason);
    expect(error).toEqual(
      expect.objectContaining({ name: "ApiError", message: expect.any(String), status: 503 }),
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(await getArt("character", reference.artID).catch((reason: unknown) => reason)).toBe(
      error,
    );
    expect(fetch).toHaveBeenCalledTimes(1);

    clearApiCache();
    expect(await getArt("character", reference.artID)).toEqual(artResponse);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("rejects successful non-JSON responses", async () => {
    spyOn(globalThis, "fetch").mockResolvedValue(new Response("<html />", { status: 200 }));
    const error = await getArt("image", "bad-response").catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toEqual(expect.objectContaining({ status: 200 }));
  });

  it("uses the compact Score routes and preserves the embedded gallery", async () => {
    const movement: MovementSummary = {
      id: "main",
      name: "For Tomorrow",
      type: "continue",
      position: 0,
      sectionCount: 1,
      startTime: 0,
      icon: null,
      logo: null,
      background: null,
      backgroundVideo: null,
    };
    const movementDetail: MovementDetail = {
      ...movement,
      items: [{ kind: "section", position: 0, section: sectionDetail }],
    };
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([movement]))
      .mockResolvedValueOnce(jsonResponse(movementDetail))
      .mockResolvedValueOnce(jsonResponse(sectionDetail))
      .mockResolvedValueOnce(jsonResponse(storyDetail));

    expect(await getMovements("EN")).toEqual([movement]);
    expect(await getMovement("EN", "main")).toEqual(movementDetail);
    expect((await getScoreSection("EN", "main", "main_17")).gallery).toEqual(galleryDetail);
    expect(await getScoreStory("EN", "main", "main_17", "main_17-1")).toEqual(storyDetail);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      apiUrl("/api/EN/scores"),
      apiUrl("/api/EN/scores/main"),
      apiUrl("/api/EN/scores/main/main_17"),
      apiUrl("/api/EN/scores/main/main_17/main_17-1"),
    ]);
  });

  it("uses compact Archive routes with hyphenated route kinds", async () => {
    const kinds: ArchiveKindSummary[] = [{ kind: "operator-record", groupCount: 1 }];
    const group: ArchiveGroupSummary = {
      id: "char_220_grani",
      name: "Grani",
      kind: "operator-record",
      type: "operator_record",
      representativeArtReference: reference,
      previewArtReferences: [reference],
    };
    const detail: ArchiveGroupDetail = {
      ...group,
      stories: [storySummary],
      artReferences: [reference],
      gallery: null,
    };
    const archiveStory: StoryDetail = {
      ...storyDetail,
      parent: {
        kind: "archive",
        archiveKind: "operator-record",
        groupID: group.id,
        groupName: group.name,
      },
    };
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(kinds))
      .mockResolvedValueOnce(jsonResponse([group]))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(archiveStory));

    expect(await getArchiveKinds("CN")).toEqual(kinds);
    expect(await getArchiveGroups("CN", "operator-record")).toEqual([group]);
    expect(await getArchiveGroup("CN", "operator-record", group.id)).toEqual(detail);
    expect(await getArchiveStory("CN", "operator-record", group.id, archiveStory.id)).toEqual(
      archiveStory,
    );
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      apiUrl("/api/CN/archives"),
      apiUrl("/api/CN/archives/operator-record"),
      apiUrl("/api/CN/archives/operator-record/char_220_grani"),
      apiUrl("/api/CN/archives/operator-record/char_220_grani/main_17-1"),
    ]);
  });

  it("loads display-owned galleries and retains stable cg IDs", async () => {
    const summary: GallerySummary = {
      id: galleryDetail.id,
      name: galleryDetail.name,
      description: galleryDetail.description,
      parent: galleryDetail.parent,
      previewThumbnailContentUrls: ["https://objects.example/cg.webp"],
    };
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([summary]))
      .mockResolvedValueOnce(jsonResponse(galleryDetail));

    expect(await getGalleries("CN")).toEqual([summary]);
    const detail = await getGallery("CN", "main/17");
    expect(detail.displays[0]?.artworks[0]).toMatchObject({
      cgID: "cg_001",
      artID: "cg_001_a/cg_001_b",
    });
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      apiUrl("/api/CN/galleries"),
      apiUrl("/api/CN/galleries/main%2F17"),
    ]);
  });

  it("loads category-qualified composite panels for slash-containing artwork IDs", async () => {
    const composite: ArtDetail = {
      ...artResponse,
      id: "panel_a/panel_b",
      category: "image",
      sourceArts: [
        { category: "image", id: "panel_a" },
        { category: "image", id: "panel_b" },
      ],
    };
    const sourceResponse = (id: string) => ({
      id,
      category: "image",
      kind: "composite_panel",
      characterID: null,
      role: null,
      variant: null,
      image: { ...artResponse.image, contentUrl: `https://objects.example/${id}.png` },
    });
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(composite))
      .mockResolvedValueOnce(jsonResponse(sourceResponse("panel_a")))
      .mockResolvedValueOnce(jsonResponse(sourceResponse("panel_b")));

    const [art, sources] = await getArtWithSources("image", composite.id);
    expect(art).toEqual(composite);
    expect(sources.map(({ id, kind }) => ({ id, kind }))).toEqual([
      { id: "panel_a", kind: "composite_panel" },
      { id: "panel_b", kind: "composite_panel" },
    ]);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      apiUrl("/api/arts/image/panel_a%2Fpanel_b"),
      apiUrl("/api/source-arts/image/panel_a"),
      apiUrl("/api/source-arts/image/panel_b"),
    ]);
  });

  it("loads and caches hierarchy-aware artwork context", async () => {
    const context: ArtContext = {
      names: ["安洁莉娜"],
      siblings: [],
      occurrences: [
        {
          parent: scoreParent,
          storyID: storySummary.id,
          storyName: storySummary.name,
          storyCode: storySummary.code,
          storyTagText: storySummary.tagText,
        },
      ],
    };
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(context));

    const first = getArtContext("CN", "character", reference.artID);
    expect(getArtContext("CN", "character", reference.artID)).toBe(first);
    expect(await first).toEqual(context);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("loads the global unreferenced artwork index once", async () => {
    const summaries = [
      {
        id: "untracked",
        category: "image" as const,
        thumbnailContentUrl: "https://objects.example/untracked.webp",
      },
    ];
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(summaries));

    const first = getUnreferencedArts();
    expect(getUnreferencedArts()).toBe(first);
    expect(await first).toEqual(summaries);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("encodes locale search queries and caches identical requests", async () => {
    const results = [
      {
        kind: "art" as const,
        id: "amiya",
        category: "character" as const,
        title: "Amiya",
        subtitle: "character",
        thumbnailContentUrl: "https://objects.example/amiya.webp",
        parent: null,
      },
    ];
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(results));
    const first = getSearchResults("EN", "Amiya & Grani");
    expect(getSearchResults("EN", "Amiya & Grani")).toBe(first);
    expect(await first).toEqual(results);
    expect(fetch.mock.calls[0]?.[0]).toBe(apiUrl("/api/EN/search?q=Amiya%20%26%20Grani"));
  });

  it("retains a failed section request across Suspense renders", async () => {
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ error: "not_found" }, 404),
    );

    const first = getScoreSection("CN", "main", "missing");
    expect(getScoreSection("CN", "main", "missing")).toBe(first);
    const error = await first.catch((reason: unknown) => reason);
    expect(error).toEqual(expect.objectContaining({ name: "ApiError", status: 404 }));
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
