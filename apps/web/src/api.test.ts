import { afterEach, describe, expect, it, mock, spyOn } from "bun:test";
import {
  getArchiveGroup,
  getArchiveGroups,
  getArchiveCategories,
  getArchiveStory,
} from "./api/archives";
import {
  getNarrativeImageAsset,
  getNarrativeImageAssetWithMaterials,
  getNarrativeImageReverseReferences,
} from "./api/images";
import { ApiError, clearApiCache, resolveApiBaseUrl } from "./api/client";
import { getGalleries, getGallery } from "./api/galleries";
import { getNarrativeMediaAsset, getNarrativeMediaReverseReferences } from "./api/media";
import { getPresentationAsset, getPresentationAssets } from "./api/presentation";
import { getSearchResults } from "./api/search";
import { getMovement, getMovements, getSection, getScoreStory } from "./api/scores";
import type {
  ArchiveGroupDetail,
  ArchiveGroupSummary,
  ArchiveCategorySummary,
  NarrativeImageReverseReferences,
  NarrativeImageAsset,
  GalleryDetail,
  GallerySummary,
  MovementDetail,
  MovementSummary,
  MediaReverseReferences,
  NarrativeMediaAsset,
  SectionDetail,
  StoryNarrativeAssetReference,
  StoryDetail,
  StorySummary,
  OrphanNarrativeAssets,
  MaterialAsset,
  PresentationAssetDetail,
  PresentationAssetSummary,
} from "./api/types";
import { getOrphanNarrativeAssets } from "./api/orphans";
import {
  assetTransitionName,
  formatBytes,
  uniqueStoryNarrativeAssetReferences,
  uniqueStoryMediaReferences,
} from "./api/utils";

const configuredApiBaseUrl = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

function apiUrl(path: string): string {
  return `${configuredApiBaseUrl}${path}`;
}

const reference: StoryNarrativeAssetReference = {
  asset: {
    namespace: "narrative",
    category: "character",
    id: "char_220_grani#5$1",
  },
  kind: "character",
  names: ["Grani"],
  previewUrl:
    "https://objects.example/ARTWORK/artwork-v1/thumbnail/character/char_220_grani%25235%25241.webp",
};

const artworkResponse: NarrativeImageAsset = {
  namespace: "narrative",
  id: reference.asset.id,
  category: reference.asset.category,
  format: "image",
  mime: "image/png",
  size: 1536,
  url: "https://objects.example/artwork.png",
  width: 100,
  height: 200,
  previewUrl:
    "https://objects.example/ARTWORK/artwork-v1/thumbnail/character/char_220_grani%25235%25241.webp",
  materials: [],
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
  previewAssetReferences: [reference],
  representativeAssetReference: reference,
};

const storyDetail: StoryDetail = {
  id: storySummary.id,
  tag: storySummary.tag,
  tagText: storySummary.tagText,
  code: storySummary.code,
  name: storySummary.name,
  info: "A story detail.",
  parent: scoreParent,
  text: "The source story text.",
  media: [
    {
      asset: { namespace: "narrative", category: "audio", id: "m_story" },
      usage: "sound",
      mime: "audio/wav",
      size: 321,
      url: "https://objects.example/m_story.wav",
    },
  ],
  imageReferences: [reference],
};

const galleryDetail: GalleryDetail = {
  id: "main_17",
  name: "Critical Phase Transition",
  description: "A gallery.",
  parent: scoreParent,
  groups: [
    {
      id: "sacrifice-torch",
      position: 0,
      name: "Sacrifice Torch",
      description: "Four artworks.",
      relatedStoryID: storySummary.id,
      relatedStageID: null,
      references: [
        {
          cgID: "cg_001",
          asset: {
            namespace: "narrative",
            category: "illustration",
            id: "cg_001_a/cg_001_b",
          },
          previewUrl: "https://objects.example/cg.webp",
        },
      ],
    },
  ],
};

const mediaDetail: NarrativeMediaAsset = {
  namespace: "narrative",
  id: "video/story.mp4",
  category: "video",
  format: "video",
  mime: "video/webm",
  size: 654,
  duration: 8.25,
  sampleRate: null,
  width: 1920,
  height: 1080,
  frameRate: 30000 / 1001,
  frameCount: 248,
  url: "https://objects.example/MEDIA/cn/video/story.webm",
};

const mediaContext: MediaReverseReferences = {
  occurrences: [
    {
      parent: scoreParent,
      storyID: storySummary.id,
      storyName: storySummary.name,
      storyCode: storySummary.code,
      storyTagText: storySummary.tagText,
    },
  ],
  collections: [scoreParent],
};

const sectionDetail: SectionDetail = {
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
  openingMedia: storyDetail.media,
  activeBackgroundVideo: null,
  stories: [storySummary],
  media: storyDetail.media,
  imageReferences: [reference],
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

  it("deduplicates qualified artwork identities while preserving first occurrence", () => {
    const sameIDOtherCategory = {
      ...reference,
      asset: { ...reference.asset, category: "illustration" as const },
    };
    expect(
      uniqueStoryNarrativeAssetReferences([reference, reference, sameIDOtherCategory]),
    ).toEqual([reference, sameIDOtherCategory]);
  });

  it("deduplicates media identities while preserving distinct kinds", () => {
    const sound = storyDetail.media[0]!;
    const music = { ...sound, usage: "music" as const };
    expect(uniqueStoryMediaReferences([sound, sound, music])).toEqual([sound]);
  });

  it("creates stable CSS-safe transition names", () => {
    expect(assetTransitionName("character", reference.asset.id)).toMatch(/^asset-[a-z0-9]+$/);
    expect(assetTransitionName("character", reference.asset.id)).toBe(
      assetTransitionName("character", reference.asset.id),
    );
    expect(assetTransitionName("illustration", reference.asset.id)).not.toBe(
      assetTransitionName("character", reference.asset.id),
    );
  });

  it("formats binary file sizes with localized numbers", () => {
    expect(formatBytes(512)).toBe("512\u00a0B");
    expect(formatBytes(1536)).toBe("1.5\u00a0KiB");
    expect(formatBytes(2 * 1024 * 1024)).toBe("2\u00a0MiB");
  });
});

describe("archive API client", () => {
  it("allows archive requests two minutes to complete", async () => {
    const timeout = spyOn(AbortSignal, "timeout");
    spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(artworkResponse));

    await getNarrativeImageAsset("character", reference.asset.id);

    expect(timeout).toHaveBeenCalledWith(120_000);
  });

  it("loads independently addressable media resources", async () => {
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(mediaDetail))
      .mockResolvedValueOnce(jsonResponse(mediaContext));

    expect(await getNarrativeMediaAsset("video", mediaDetail.id)).toEqual(mediaDetail);
    expect(await getNarrativeMediaReverseReferences("CN", "video", mediaDetail.id)).toEqual(
      mediaContext,
    );
    expect(fetch.mock.calls[0]?.[0]).toBe(apiUrl("/api/assets/narrative/video/video%2Fstory.mp4"));
    expect(fetch.mock.calls[1]?.[0]).toBe(
      apiUrl("/api/CN/assets/narrative/video/video%2Fstory.mp4/reverse-references"),
    );
  });

  it("encodes artwork IDs and deduplicates in-flight requests", async () => {
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(artworkResponse));

    const first = getNarrativeImageAsset("character", reference.asset.id);
    const second = getNarrativeImageAsset("character", reference.asset.id);

    expect(first).toBe(second);
    expect(await first).toEqual(artworkResponse);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[0]).toBe(
      apiUrl("/api/assets/narrative/character/char_220_grani%235%241"),
    );
  });

  it("retains failed requests until an explicit retry clears the cache", async () => {
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ error: "service_unavailable" }, 503))
      .mockResolvedValueOnce(jsonResponse(artworkResponse));

    const error = await getNarrativeImageAsset("character", reference.asset.id).catch(
      (reason: unknown) => reason,
    );
    expect(error).toEqual(
      expect.objectContaining({ name: "ApiError", message: expect.any(String), status: 503 }),
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(
      await getNarrativeImageAsset("character", reference.asset.id).catch(
        (reason: unknown) => reason,
      ),
    ).toBe(error);
    expect(fetch).toHaveBeenCalledTimes(1);

    clearApiCache();
    expect(await getNarrativeImageAsset("character", reference.asset.id)).toEqual(artworkResponse);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("rejects successful non-JSON responses", async () => {
    spyOn(globalThis, "fetch").mockResolvedValue(new Response("<html />", { status: 200 }));
    const error = await getNarrativeImageAsset("illustration", "bad-response").catch(
      (reason: unknown) => reason,
    );
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
    expect((await getSection("EN", "main", "main_17")).gallery).toEqual(galleryDetail);
    expect(await getScoreStory("EN", "main", "main_17", "main_17-1")).toEqual(storyDetail);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      apiUrl("/api/EN/scores"),
      apiUrl("/api/EN/scores/main"),
      apiUrl("/api/EN/scores/main/main_17"),
      apiUrl("/api/EN/scores/main/main_17/main_17-1"),
    ]);
  });

  it("uses compact Archive routes with hyphenated categories", async () => {
    const categories: ArchiveCategorySummary[] = [
      { archiveCategory: "operator-record", groupCount: 1 },
    ];
    const group: ArchiveGroupSummary = {
      id: "char_220_grani",
      name: "Grani",
      archiveCategory: "operator-record",
      type: "operator_record",
      representativeAssetReference: reference,
      previewAssetReferences: [reference],
    };
    const detail: ArchiveGroupDetail = {
      ...group,
      stories: [storySummary],
      media: storyDetail.media,
      imageReferences: [reference],
      openingMedia: storyDetail.media,
      gallery: null,
    };
    const archiveStory: StoryDetail = {
      ...storyDetail,
      parent: {
        kind: "archive",
        archiveCategory: "operator-record",
        groupID: group.id,
        groupName: group.name,
      },
    };
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(categories))
      .mockResolvedValueOnce(jsonResponse([group]))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(archiveStory));

    expect(await getArchiveCategories("CN")).toEqual(categories);
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

  it("loads Gallery Group-owned artwork and retains stable cg IDs", async () => {
    const summary: GallerySummary = {
      id: galleryDetail.id,
      name: galleryDetail.name,
      description: galleryDetail.description,
      parent: galleryDetail.parent,
      previewUrls: ["https://objects.example/cg.webp"],
    };
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([summary]))
      .mockResolvedValueOnce(jsonResponse(galleryDetail));

    expect(await getGalleries("CN")).toEqual([summary]);
    const detail = await getGallery("CN", "main/17");
    expect(detail.groups[0]?.references[0]).toMatchObject({
      cgID: "cg_001",
      asset: { id: "cg_001_a/cg_001_b" },
    });
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      apiUrl("/api/CN/galleries"),
      apiUrl("/api/CN/galleries/main%2F17"),
    ]);
  });

  it("loads category-qualified source panels for slash-containing artwork IDs", async () => {
    const panelArtwork: NarrativeImageAsset = {
      ...artworkResponse,
      id: "panel_a/panel_b",
      category: "illustration",
      materials: [
        { namespace: "material", category: "illustration", id: "panel_a" },
        { namespace: "material", category: "illustration", id: "panel_b" },
      ],
    };
    const sourceResponse = (id: string): MaterialAsset => ({
      namespace: "material",
      id,
      category: "illustration",
      format: "image",
      mime: "image/png",
      size: 1536,
      url: `https://objects.example/${id}.png`,
      width: 100,
      height: 200,
      materialType: "panel",
      characterID: null,
      role: null,
      variant: null,
      reverseReferences: [
        { namespace: "narrative", category: "illustration", id: panelArtwork.id },
      ],
    });
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(panelArtwork))
      .mockResolvedValueOnce(jsonResponse(sourceResponse("panel_a")))
      .mockResolvedValueOnce(jsonResponse(sourceResponse("panel_b")));

    const [artwork, sources] = await getNarrativeImageAssetWithMaterials(
      "illustration",
      panelArtwork.id,
    );
    expect(artwork).toEqual(panelArtwork);
    expect(sources.map(({ id, materialType }) => ({ id, materialType }))).toEqual([
      { id: "panel_a", materialType: "panel" },
      { id: "panel_b", materialType: "panel" },
    ]);
    expect(sources[0]?.reverseReferences).toEqual([
      { namespace: "narrative", category: "illustration", id: panelArtwork.id },
    ]);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      apiUrl("/api/assets/narrative/illustration/panel_a%2Fpanel_b"),
      apiUrl("/api/assets/material/illustration/panel_a"),
      apiUrl("/api/assets/material/illustration/panel_b"),
    ]);
  });

  it("loads and caches hierarchy-aware Artwork Reverse References", async () => {
    const reverseReferences: NarrativeImageReverseReferences = {
      names: ["安洁莉娜"],
      characterVariants: [],
      textures: [],
      galleries: [],
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
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(reverseReferences));

    const first = getNarrativeImageReverseReferences("CN", "character", reference.asset.id);
    expect(getNarrativeImageReverseReferences("CN", "character", reference.asset.id)).toBe(first);
    expect(await first).toEqual(reverseReferences);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("loads and caches all six orphan narrative asset categories", async () => {
    const assets: OrphanNarrativeAssets = [
      {
        namespace: "narrative",
        id: "untracked",
        category: "illustration",
        format: "image",
        mime: "image/png",
        size: 456,
        url: "https://objects.example/untracked.png",
        width: 100,
        height: 200,
        previewUrl: "https://objects.example/untracked.webp",
      },
      {
        namespace: "narrative",
        id: "unused-audio",
        category: "audio",
        format: "audio",
        mime: "audio/wav",
        size: 123,
        url: "https://objects.example/unused.wav",
      },
    ];
    const fetch = spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse(assets));

    const first = getOrphanNarrativeAssets("CN");
    expect(getOrphanNarrativeAssets("CN")).toBe(first);
    expect(await first).toEqual(assets);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[0]).toBe(apiUrl("/api/CN/orphans"));
  });

  it("encodes locale search queries and caches identical requests", async () => {
    const results = [
      {
        kind: "narrative_asset" as const,
        id: "amiya",
        category: "character" as const,
        title: "Amiya",
        subtitle: "character",
        previewUrl: "https://objects.example/amiya.webp",
        parent: null,
      },
    ];
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(results));
    const first = getSearchResults("EN", "Amiya & Grani");
    expect(getSearchResults("EN", "Amiya & Grani")).toBe(first);
    expect(await first).toEqual(results);
    expect(fetch.mock.calls[0]?.[0]).toBe(apiUrl("/api/EN/search?q=Amiya%20%26%20Grani"));
  });

  it("lists and loads presentation assets with encoded identifiers", async () => {
    const summary: PresentationAssetSummary = {
      namespace: "presentation",
      category: "key-visual",
      id: "main/17#kv",
      format: "image",
      mime: "image/png",
      size: 4096,
      width: 1920,
      height: 1080,
      duration: null,
      referenceCount: 1,
      previewUrl: "https://objects.example/key-visual.webp",
    };
    const detail: PresentationAssetDetail = {
      ...summary,
      url: "https://objects.example/key-visual.png",
      frameRate: null,
      frameCount: null,
      reverseReferences: [
        {
          ownerType: "section",
          ownerID: "main_17",
          movementID: "main",
          role: "key-visual",
          name: "Critical Phase Transition",
        },
      ],
    };
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([summary]))
      .mockResolvedValueOnce(jsonResponse(detail));

    expect(await getPresentationAssets("EN")).toEqual([summary]);
    expect(await getPresentationAsset("EN", "key-visual", summary.id)).toEqual(detail);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      apiUrl("/api/EN/assets/presentation"),
      apiUrl("/api/EN/assets/presentation/key-visual/main%2F17%23kv"),
    ]);
  });

  it("retains a failed section request across Suspense renders", async () => {
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ error: "not_found" }, 404),
    );

    const first = getSection("CN", "main", "missing");
    expect(getSection("CN", "main", "missing")).toBe(first);
    const error = await first.catch((reason: unknown) => reason);
    expect(error).toEqual(expect.objectContaining({ name: "ApiError", status: 404 }));
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
