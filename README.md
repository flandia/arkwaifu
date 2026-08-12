<!--suppress ALL -->
<img src="assets/arkwaifu_phantom@0.25x.png" alt="logo" align="right" height="224" width="224"/>

# Arkwaifu (arkwaifu)

![](https://img.shields.io/github/license/flandia/arkwaifu?style=flat-square)
![](https://img.shields.io/github/v/release/flandia/arkwaifu?style=flat-square)

![](https://img.shields.io/github/actions/workflow/status/flandia/arkwaifu/docker-image-service.yml?style=flat-square&label=build%3A%20service)
![](https://img.shields.io/github/actions/workflow/status/flandia/arkwaifu/docker-image-updateloop.yml?style=flat-square&label=build%3A%20updateloop)
![](https://img.shields.io/github/actions/workflow/status/flandia/arkwaifu/web.yml?style=flat-square&label=build%3A%20web)
![](https://img.shields.io/website?style=flat-square&url=https%3A%2F%2Farkwaifu.cc%2F)

Arkwaifu is a website which arranges and provides artwork and localized story
metadata extracted from Arknights.

This branch is a breaking rewrite. A Python 3.14 updateloop publishes native
PNG artwork and one SQLite database to S3-compatible storage, and an OCaml 5.5
Dream service provides the HTTP API. A React 19 and React Router frontend
presents the archive and provides client-side story and gallery filtering.
Global server-side search remains deferred. The previous frontend is retained
in its [historical repository](https://github.com/flandia/arkwaifu-frontend).

🎉 Arkwaifu v2 has released! Check it at [arkwaifu.cc](https://arkwaifu.cc/)!

## Features

- Art and all supported locales can be updated automatically.
- Final PNG compositions and original character body, face, and whole-body
  layers are retained.
- Cards use updater-generated WebP thumbnails while detail views retain the
  full PNG compositions.
- Story and gallery metadata is available in CN, EN, JP, KR, and TW.
- The responsive React frontend supports localized archive browsing and
  client-side index filtering.

## Available Arts

Arts that appear in in-game stories are available, including **images**,
**backgrounds**, **items**, and **characters**. The examples below use the v1
website interface; the rewrite is intentionally not API-compatible.

### Images

Images are the exquisite artworks that appear when some special events in the stories happen.

<img src="https://arkwaifu.cc/api/v1/arts/32_i18/variants/origin/content" width="800"/>

### Backgrounds

Backgrounds are the artworks that always appear during dialogue between characters.

<img src="https://arkwaifu.cc/api/v1/arts/bg_courtyard/variants/origin/content" width="800"/>

### Items

Items are illustrations of objects that appear in stories.

### Characters

Characters are the artworks that represent characters who appear during
dialogue. The rewrite retains both the final composition and its original
source layers.

<img src="https://arkwaifu.cc/api/v1/arts/char_250_phantom_1%233%241/variants/origin/content" width="800"/>

## Roadmap

- [x] Switchable language.
- [x] Switchable archive locale.
- [x] A new frontend.
- [ ] Add global server-side search.

## Development

See the [updateloop documentation](apps/updateloop/README.md), [service
documentation](apps/service/README.md), and [web documentation](apps/web/README.md).

## Acknowledgements

Thanks to my friend [Galvin Gao](https://github.com/GalvinGao)!
He helped me a lot in the front-end development and choosing frameworks. I really appreciate the "getting hands dirty"
methodology very much.

Thanks to my friend [Martin Wang](https://github.com/martinwang2002)!
He helped me in extracting the gamedata assets, and also in some details of automatically updating the assets from the
game.

Thanks to my friend Lily! She drew the fascinating [Phantom logo](assets/arkwaifu_phantom.png) of this project.

Thanks to [Penguin Statistics](https://penguin-stats.io/)!
The prototype of this project referenced and is inspired by Penguin
Statistics' [backend v3](https://github.com/penguin-statistics/backend-next).

Thanks to [xinntao](https://github.com/xinntao), [nihui](https://github.com/nihui), and the other contributors
of [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)
and [Real-CUGAN](https://github.com/bilibili/ailab/tree/main/Real-CUGAN)!
Earlier versions of Arkwaifu used their neural networks for enlarging assets.

## License

The source code of this project is licensed under the [MIT License](LICENSE).

The assets of this project are licensed under
[Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/).

This project utilizes resources and other works from the game Arknights. The copyright of such works belongs to the
provider of the game, 上海鹰角网络科技有限公司 (Shanghai Hypergryph Network Technology Co., Ltd).

Earlier versions utilized [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)
and [Real-ESRGAN-ncnn-vulkan](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan), which are respectively licensed under
the BSD-3-Clause license and the MIT License.

Earlier versions utilized [Real-CUGAN](https://github.com/bilibili/ailab/tree/main/Real-CUGAN)
and [Real-CUGAN-ncnn-vulkan](https://github.com/nihui/realcugan-ncnn-vulkan), which are both licensed under the MIT
License.

Some initial template source code of this project is inspired by and copied from
the [backend v3](https://github.com/penguin-statistics/backend-next) of [Penguin Statistics](https://penguin-stats.io/),
which is licensed under the [MIT License](https://github.com/penguin-statistics/backend-next/blob/dev/LICENSE).
