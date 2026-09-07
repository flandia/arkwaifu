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
