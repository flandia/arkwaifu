import { afterEach, describe, expect, it, mock, spyOn } from "bun:test";
import {
  ApiError,
  artTransitionName,
  clearApiCache,
  formatBytes,
  getArt,
  getArtContext,
  getGroupData,
  getStoryGroup,
  getUnclassifiedArts,
  uniqueArtReferences,
  type ArtReference,
} from "./api";

const reference: ArtReference = {
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
  it("deduplicates qualified art identities while preserving first occurrence", () => {
    const sameIDOtherCategory = { ...reference, category: "image" as const };
    expect(uniqueArtReferences([reference, reference, sameIDOtherCategory])).toEqual([
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
    expect(fetch.mock.calls[0]?.[0]).toBe(
      "https://api.arkwaifu.cc/api/arts/character/char_220_grani%235%241",
    );
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
    const group = {
      id: "main_17",
      name: "相变临界",
      type: "main_story" as const,
      previewArtReferences: [reference],
      representativeArtReference: reference,
      artReferences: [reference],
    };
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(group));

    expect(await getStoryGroup("CN", group.id)).toEqual(group);
    expect(fetch.mock.calls[0]?.[0]).toBe("https://api.arkwaifu.cc/api/CN/story-groups/main_17");
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
      "https://api.arkwaifu.cc/api/CN/arts/character/char_220_grani%235%241/context",
    );
  });

  it("loads the global unclassified artwork index once", async () => {
    const summaries = [
      {
        id: "untracked",
        category: "image" as const,
        thumbnailContentUrl: "https://objects.example/untracked.webp",
      },
    ];
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(summaries));

    const first = getUnclassifiedArts();
    const second = getUnclassifiedArts();

    expect(first).toBe(second);
    expect(await first).toEqual(summaries);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[0]).toBe("https://api.arkwaifu.cc/api/unclassified-arts");
  });

  it("retains a missing group-page request instead of retrying during Suspense renders", async () => {
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ error: "not_found" }, 404),
    );

    const first = getGroupData("CN", "missing");
    const second = getGroupData("CN", "missing");
    expect(first).toBe(second);
    const error = await first.catch((reason: unknown) => reason);
    expect(error).toEqual(expect.objectContaining({ name: "ApiError", status: 404 }));
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(getGroupData("CN", "missing")).toBe(first);
  });
});
