import { expect, it } from "bun:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";

it("links available story and orphan audio to their asset details", async () => {
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: { documentElement: { lang: "" } },
  });
  const { StoryMediaCollection, MediaResourceCollection } = await import("./MediaCollection");
  const audio = {
    namespace: "narrative" as const,
    category: "audio" as const,
    format: "audio" as const,
    id: "music/theme #1",
    mime: "audio/wav",
    size: 1024,
    url: "https://objects.example/theme.wav",
  };
  const storyMarkup = renderToStaticMarkup(
    createElement(
      MemoryRouter,
      null,
      createElement(StoryMediaCollection, {
        from: "/EN/scores/main/chapter",
        locale: "EN",
        media: [
          { asset: audio, mime: audio.mime, size: audio.size, url: audio.url },
          { asset: { ...audio, id: "unavailable" } },
        ],
      }),
    ),
  );
  const orphanMarkup = renderToStaticMarkup(
    createElement(
      MemoryRouter,
      null,
      createElement(MediaResourceCollection, { from: "/EN/orphans", locale: "EN", media: [audio] }),
    ),
  );

  for (const markup of [storyMarkup, orphanMarkup]) {
    expect(markup).toContain('href="/EN/assets/narrative/audio/music%2Ftheme%20%231"');
    expect(markup).toContain('controls=""');
  }
  expect(storyMarkup).not.toContain('href="/EN/assets/narrative/audio/unavailable"');
});

it("keeps both metadata fields on audio cards when values are missing", async () => {
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: { documentElement: { lang: "" } },
  });
  const { StoryMediaCollection } = await import("./MediaCollection");
  const asset = { namespace: "narrative" as const, category: "audio" as const, id: "missing" };
  const cases = [
    { fields: {}, values: ["N/A", "N/A"] },
    { fields: { mime: "audio/wav" }, values: ["audio/wav", "N/A"] },
    { fields: { size: 1024 }, values: ["N/A", "1\u00a0KiB"] },
    { fields: { mime: "audio/wav", size: 0 }, values: ["audio/wav", "0\u00a0B"] },
  ];

  for (const { fields, values } of cases) {
    const markup = renderToStaticMarkup(
      createElement(
        MemoryRouter,
        null,
        createElement(StoryMediaCollection, {
          from: "/EN/scores/main/chapter",
          locale: "EN",
          media: [{ asset, ...fields }],
        }),
      ),
    );
    expect(markup).toContain(`<span>${values[0]}</span><span>${values[1]}</span>`);
    expect(markup).not.toContain('href="/EN/assets/narrative/audio/missing"');
  }
});
