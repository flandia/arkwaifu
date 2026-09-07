import { afterEach, beforeEach, expect, it, mock, spyOn } from "bun:test";
import { downloadFile } from "./download";

const anchor = { href: "", download: "", click: mock(), remove: mock() };
let release: (() => void) | undefined;
let documentDescriptor: PropertyDescriptor | undefined;
let windowDescriptor: PropertyDescriptor | undefined;

beforeEach(() => {
  documentDescriptor = Object.getOwnPropertyDescriptor(globalThis, "document");
  windowDescriptor = Object.getOwnPropertyDescriptor(globalThis, "window");
  anchor.href = "";
  anchor.download = "";
  anchor.click.mockClear();
  anchor.remove.mockClear();
  release = undefined;
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: { createElement: () => anchor, body: { append: mock() } },
  });
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { setTimeout: (callback: () => void) => (release = callback) },
  });
});

afterEach(() => {
  mock.restore();
  for (const [key, descriptor] of [
    ["document", documentDescriptor],
    ["window", windowDescriptor],
  ] as const) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else Reflect.deleteProperty(globalThis, key);
  }
});

it("downloads through a Blob URL and releases it after browser handoff", async () => {
  const fetchMock = spyOn(globalThis, "fetch").mockResolvedValue(
    new Response("audio", { headers: { "Content-Type": "audio/wav" } }),
  );
  const createUrl = spyOn(URL, "createObjectURL").mockReturnValue("blob:download");
  const revokeUrl = spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  const signal = new AbortController().signal;
  await downloadFile("https://objects.example/theme%231.wav", signal);

  expect(fetchMock).toHaveBeenCalledWith("https://objects.example/theme%231.wav", { signal });
  expect(createUrl.mock.calls[0]?.[0]).toBeInstanceOf(Blob);
  expect(anchor.href).toBe("blob:download");
  expect(anchor.download).toBe("theme#1.wav");
  expect(anchor.click).toHaveBeenCalledTimes(1);
  expect(anchor.remove).toHaveBeenCalledTimes(1);
  expect(revokeUrl).not.toHaveBeenCalled();
  release?.();
  expect(revokeUrl).toHaveBeenCalledWith("blob:download");
});

it("does not save an error response as an original file", async () => {
  spyOn(globalThis, "fetch").mockResolvedValue(new Response("Unavailable", { status: 503 }));
  const error = await downloadFile(
    "https://objects.example/file.png",
    new AbortController().signal,
  ).catch((reason: unknown) => reason);
  expect(error).toEqual(new Error("Download failed: 503"));
  expect(anchor.click).not.toHaveBeenCalled();
});

it("does not start a browser download after the request is cancelled", async () => {
  const controller = new AbortController();
  spyOn(globalThis, "fetch").mockResolvedValue(new Response("audio"));
  const request = downloadFile("https://objects.example/file.wav", controller.signal);
  controller.abort();
  const error = await request.catch((reason: unknown) => reason);
  expect(error).toBeInstanceOf(DOMException);
  expect(anchor.click).not.toHaveBeenCalled();
});
