import { expect, it } from "bun:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

it("offers a playback control and omits decorative video for reduced motion", async () => {
  const documentDescriptor = Object.getOwnPropertyDescriptor(globalThis, "document");
  const windowDescriptor = Object.getOwnPropertyDescriptor(globalThis, "window");
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: { documentElement: { lang: "" } },
  });
  let reducedMotion = false;
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { matchMedia: () => ({ matches: reducedMotion }) },
  });
  try {
    const { ScoreBackdrop } = await import("./ScoreVisual");
    const backdrop = createElement(ScoreBackdrop, {
      image: null,
      video: {
        namespace: "presentation",
        category: "video",
        id: "background",
        video: {
          mime: "video/webm",
          size: 1000,
          width: 1920,
          height: 1080,
          frameRate: 30,
          frameCount: 1800,
          url: "https://objects.example/background.webm",
        },
      },
    });
    const animated = renderToStaticMarkup(backdrop);
    expect(animated).toContain("<video");
    expect(animated).toContain("</div><button");
    reducedMotion = true;
    const still = renderToStaticMarkup(backdrop);
    expect(still).not.toContain("<video");
    expect(still).not.toContain("<button");
  } finally {
    for (const [key, descriptor] of [
      ["document", documentDescriptor],
      ["window", windowDescriptor],
    ] as const) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  }
});
