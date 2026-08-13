import { describe, expect, it } from "bun:test";
import { canonicalUrl } from "./seo";

describe("canonicalUrl", () => {
  it("removes query strings, fragments, and trailing slashes", () => {
    expect(canonicalUrl("/CN/stories/main/?order=archive#image")).toBe(
      "https://arkwaifu.cc/CN/stories/main",
    );
  });

  it("keeps the site root and makes relative paths root-relative", () => {
    expect(canonicalUrl("/")).toBe("https://arkwaifu.cc/");
    expect(canonicalUrl("CN/about")).toBe("https://arkwaifu.cc/CN/about");
  });
});
