import { describe, expect, it } from "bun:test";

describe("story navigation", () => {
  it("maps every story group type to its public route", async () => {
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: { documentElement: { lang: "" } },
    });
    const { sectionForType, storySections } = await import("./navigation");

    expect(
      Object.fromEntries(
        Object.values(storySections).map(({ type }) => [type, sectionForType(type)]),
      ),
    ).toEqual({
      main_story: "main",
      major_event: "events",
      minor_event: "vignettes",
      operator_record: "records",
      integrated_strategies: "integrated-strategies",
      reclamation_algorithm: "reclamation-algorithm",
      others: "others",
    });
  });
});
