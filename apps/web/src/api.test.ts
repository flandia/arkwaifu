import { afterEach, describe, expect, it, mock, spyOn } from "bun:test";
import {
  ApiError,
  artTransitionName,
  clearApiCache,
  formatBytes,
  getArt,
  getArtContext,
  getStoriesByGroup,
  getStory,
  getStoryGroup,
  getStoryGroupWithStories,
  getUnreferencedArts,
  uniqueStoryArtReferences,
  type StoryArtReference,
  type StoryDetail,
  type StoryGroupDetail,
  type StorySummary,
} from "./api";
import { resolveApiBaseUrl } from "./api/client";

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

const artResponse = {
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
  sourceArtIDs: [],
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
    expect(resolveApiBaseUrl(" https://preview.example.test/root/// ")).toBe(
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
    expect(fetch.mock.calls[0]?.[1]).toMatchObject({ headers: { Accept: "application/json" } });
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

    const cachedError = await getArt("character", reference.artID).catch(
      (reason: unknown) => reason,
    );
    expect(cachedError).toBe(error);
    expect(fetch).toHaveBeenCalledTimes(1);

    clearApiCache();
    expect(await getArt("character", reference.artID)).toEqual(artResponse);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("rejects successful non-JSON responses", async () => {
    spyOn(globalThis, "fetch").mockResolvedValue(new Response("<html />", { status: 200 }));
    const error = await getArt("image", "bad-response").catch((reason: unknown) => reason);
    expect(error).toEqual(
      expect.objectContaining({ name: "ApiError", message: expect.any(String), status: 200 }),
    );
    expect(error).toBeInstanceOf(ApiError);
  });

  it("loads aggregate story-group artwork through the detail route", async () => {
    const group: StoryGroupDetail = {
      id: "main_17",
      name: "相变临界",
      type: "main_story" as const,
      previewArtReferences: [reference],
      representativeArtReference: reference,
      artReferences: [reference],
    };
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(group));

    expect(await getStoryGroup("CN", group.id)).toEqual(group);
    expect(fetch.mock.calls[0]?.[0]).toBe(apiUrl("/api/CN/story-groups/main_17"));
  });

  it("keeps story summary and detail endpoint shapes distinct", async () => {
    const detail: StoryDetail = {
      id: "main_17-1",
      groupID: "main_17",
      tag: "before",
      tagText: "Before Operation",
      code: "17-1",
      name: "Seeds",
      info: "A story detail.",
      artReferences: [reference],
    };
    const summary: StorySummary = {
      id: detail.id,
      groupID: detail.groupID,
      tag: detail.tag,
      tagText: detail.tagText,
      code: detail.code,
      name: detail.name,
      info: detail.info,
      artReferences: [],
      previewArtReferences: [reference],
      representativeArtReference: reference,
    };
    const fetch = spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([summary]))
      .mockResolvedValueOnce(jsonResponse(detail));

    expect(await getStoriesByGroup("EN", detail.groupID)).toEqual([summary]);
    expect(await getStory("EN", detail.id)).toEqual(detail);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      apiUrl("/api/EN/story-groups/main_17/stories"),
      apiUrl("/api/EN/stories/main_17-1"),
    ]);
  });

  it("loads and caches localized artwork context", async () => {
    const context = {
      names: ["安洁莉娜"],
      siblings: [
        {
          artID: "avg_1015_aglna2_1#12$2",
          names: ["安洁莉娜"],
          thumbnailContentUrl: "https://objects.example/angelina.webp",
        },
      ],
      occurrences: [
        {
          groupID: "act53side",
          groupName: "挽歌燃烧殆尽",
          groupType: "major_event" as const,
          storyID: "act53side_level_st_01",
          storyName: "序曲",
          storyCode: "ST-1",
          storyTagText: "剧情",
        },
      ],
    };
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(context));

    const first = getArtContext("CN", "character", reference.artID);
    const second = getArtContext("CN", "character", reference.artID);

    expect(first).toBe(second);
    expect(await first).toEqual(context);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[0]).toBe(
      apiUrl("/api/CN/arts/character/char_220_grani%235%241/context"),
    );
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
    const second = getUnreferencedArts();

    expect(first).toBe(second);
    expect(await first).toEqual(summaries);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[0]).toBe(apiUrl("/api/unreferenced-arts"));
  });

  it("retains a missing group-page request instead of retrying during Suspense renders", async () => {
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ error: "not_found" }, 404),
    );

    const first = getStoryGroupWithStories("CN", "missing");
    const second = getStoryGroupWithStories("CN", "missing");
    expect(first).toBe(second);
    const error = await first.catch((reason: unknown) => reason);
    expect(error).toEqual(expect.objectContaining({ name: "ApiError", status: 404 }));
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(getStoryGroupWithStories("CN", "missing")).toBe(first);
  });
});
