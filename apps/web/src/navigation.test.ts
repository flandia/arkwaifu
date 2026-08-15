import { describe, expect, it } from "bun:test";

Object.defineProperty(globalThis, "document", {
  configurable: true,
  value: { documentElement: { lang: "" } },
});

describe("archive navigation", () => {
  it("matches a Movement route by complete path segment", async () => {
    const { isPathAtOrBelow } = await import("./navigation");

    expect(isPathAtOrBelow("/CN/scores/ssline_1", "/CN/scores/ssline_1")).toBe(true);
    expect(isPathAtOrBelow("/CN/scores/ssline_1/section", "/CN/scores/ssline_1")).toBe(true);
    expect(isPathAtOrBelow("/CN/scores/ssline_10", "/CN/scores/ssline_1")).toBe(false);
  });

  it("recognizes every public Archive kind and rejects removed story-section slugs", async () => {
    const { archiveKinds, isArchiveKind } = await import("./navigation");

    expect(Object.keys(archiveKinds)).toEqual([
      "events",
      "operator-record",
      "integrated-strategies",
      "reclamation-algorithm",
      "others",
    ]);
    expect(Object.keys(archiveKinds).every(isArchiveKind)).toBe(true);
    expect(isArchiveKind("main")).toBe(false);
    expect(isArchiveKind("vignettes")).toBe(false);
  });

  it("builds hierarchy-owned Score and Archive story paths", async () => {
    const { storyParentPath, storyPath } = await import("./navigation");
    const scoreParent = {
      kind: "score" as const,
      movementID: "main/line",
      movementName: "For Tomorrow",
      sectionID: "main 17",
      sectionName: "Critical Phase Transition",
    };
    const archiveParent = {
      kind: "archive" as const,
      archiveKind: "operator-record" as const,
      groupID: "char/220",
      groupName: "Grani",
    };

    expect(storyParentPath("EN", scoreParent)).toBe("/EN/scores/main%2Fline/main%2017");
    expect(storyPath("EN", scoreParent, "story/1")).toBe(
      "/EN/scores/main%2Fline/main%2017/story%2F1",
    );
    expect(storyPath("CN", archiveParent, "story 1")).toBe(
      "/CN/archives/operator-record/char%2F220/story%201",
    );
  });
});
