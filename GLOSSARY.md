# Arkwaifu 词汇表

## 资源模型 / Asset Model

| 名词 | 定义 | 例子 |
| --- | --- | --- |
| 资源 / Asset | 一项可以单独打开、展示或下载的文件记录。 | 角色图片 `char_220_grani#5$1`、剧情音频 `m_story`、乐章图标 `icon-main`。 |
| 资源命名空间 / Asset Namespace | 资源身份的第一级范围。它区分叙事性资源、制作素材和展示性资源。 | `narrative`、`material`、`presentation`。两个命名空间可以使用相同的类别和 ID。 |
| 叙事资源 / Narrative Asset | 命名空间为 `narrative` 的叙事性资源。 | 插画、背景、物件、角色、剧情视频和剧情音频。 |
| 素材 / Material Asset | 命名空间为 `material` 的图片输入，用于生成成品图片。 | 一张角色脸部素材或一块拼图面板。 |
| 展示资源 / Presentation Asset | 命名空间为 `presentation` 的展示性资源，用于曲谱层级页面。 | 乐章图标、乐部主视觉和乐章分段视频。 |
| 资源类别 / Asset Category | 一个命名空间内的语义分类，也是资源身份的一部分。 | `narrative` 中的 `character`；`presentation` 中的 `key-visual`。 |
| 资源格式 / Asset Format | 浏览器展示文件的方式。它不参与资源身份。 | `image`、`video`、`audio`。插画的类别是 `illustration`，格式是 `image`。 |
| 资源 ID / Asset ID | 上游为资源提供的逻辑标识。ID 不是文件名、内容哈希或网址片段。 | `char_220_grani#5$1`。它在 `narrative + character` 内唯一。 |
| 资源身份 / Asset Identity | 唯一定位资源的 `(namespace, category, id)` 三元组。 | `(narrative, character, char_220_grani#5$1)`。 |
| 资源引用 / Asset Reference | 指向一个资源身份的结构化记录。引用可以补充顺序、用途或显示名称。 | 一条剧情引用指向 `(narrative, character, char_220_grani#5$1)`，并记录角色名“砾”。 |
| 反向引用 / Reverse References | 从一个资源查找所有指向它的资源引用。 | 角色图片详情页列出引用它的剧情和画廊。 |
| 资源目录 / Asset Catalog | 按命名空间列出资源的只读页面和列表接口。它支持筛选和打开详情，但不创建引用。 | 展示资源目录列出所有 `presentation` 资源，并按类别筛选。 |
| 孤立叙事资源 / Orphan Narrative Asset | 当前语言中没有剧情引用、合集引用或画廊引用的叙事资源。 | `/CN/orphans` 中的一张背景图。该状态由反向引用计算，不表示数据损坏。 |

### 资源记录 / Asset Record

每个资源记录都包含相同的身份字段和文件字段。“相同”只表示接口字段一致，不表示图片、视频和音频具有相同的格式专有元数据。例如：

```json
{
  "namespace": "narrative",
  "category": "character",
  "id": "char_220_grani#5$1",
  "format": "image",
  "mime": "image/png",
  "size": 1048576,
  "url": "https://objects.example/character/char_220_grani.png"
}
```

`namespace`、`category` 和 `id` 组成资源身份。`format` 决定前端使用图片、视频还是音频视图。`mime` 是具体的媒体类型，例如 `image/png`。`size` 是文件字节数。`url` 指向可打开或下载的文件。

图片记录另外包含 `width` 和 `height`。视频记录另外包含尺寸、帧率、帧数和时长。音频记录另外包含采样率和时长。

### 三个资源命名空间 / Asset Namespaces

| 资源命名空间 / Asset Namespace | 资源类别 / Asset Category | 资源格式 / Asset Format |
| --- | --- | --- |
| 叙事 / Narrative (`narrative`) | 插画 / Illustration (`illustration`)、背景 / Background (`background`)、物件 / Item (`item`)、角色 / Character (`character`) | 图片 / Image (`image`) |
| 叙事 / Narrative (`narrative`) | 视频 / Video (`video`) | 视频 / Video (`video`) |
| 叙事 / Narrative (`narrative`) | 音频 / Audio (`audio`) | 音频 / Audio (`audio`) |
| 素材 / Material (`material`) | 插画 / Illustration (`illustration`)、背景 / Background (`background`)、物件 / Item (`item`)、角色 / Character (`character`) | 图片 / Image (`image`) |
| 展示 / Presentation (`presentation`) | 图标 / Icon (`icon`)、标志 / Logo (`logo`)、背景 / Background (`background`)、主视觉 / Key Visual (`key-visual`)、标题 / Title (`title`)、装饰 / Decoration (`decoration`)、复古背景 / Retro Background (`retro-background`)、分隔图 / Divider (`divider`) | 图片 / Image (`image`) |
| 展示 / Presentation (`presentation`) | 视频 / Video (`video`) | 视频 / Video (`video`) |

叙事资源是叙事性的内容。展示资源来自游戏界面，用于乐章、乐部和乐章分段的页面展示。素材是生成叙事图片时保留的输入图片。

### 资源身份示例 / Asset Identity Examples

| 资源命名空间 / Asset Namespace | 资源类别 / Asset Category | 资源 ID / Asset ID | 网址示例 / URL Example |
| --- | --- | --- | --- |
| 叙事 / Narrative (`narrative`) | 角色 / Character (`character`) | `char_220_grani#5$1` | `/CN/assets/narrative/character/char_220_grani%235%241` |
| 叙事 / Narrative (`narrative`) | 音频 / Audio (`audio`) | `m_story` | `/CN/assets/narrative/audio/m_story` |
| 素材 / Material (`material`) | 插画 / Illustration (`illustration`) | `panel_source` | `/CN/assets/material/illustration/panel_source` |
| 展示 / Presentation (`presentation`) | 主视觉 / Key Visual (`key-visual`) | `kv-section` | `/CN/assets/presentation/key-visual/kv-section` |

资源 ID 保留上游原值。网址把整个 ID 编码为一个路径段，因此 `#` 写成 `%23`，`$` 写成 `%24`，ID 内的 `/` 写成 `%2F`。下划线不需要改变。

## 资源引用 / Asset References

通用资源引用就是一个资源身份：

```json
{
  "namespace": "narrative",
  "category": "character",
  "id": "char_220_grani#5$1"
}
```

一个所有者可以返回多条资源引用。接口按照上游顺序排列数组，前端直接使用数组顺序。数据库内部可以用 `position` 恢复这个顺序，但公共资源引用不返回 `position`。

只有特定引用才增加上下文。例如，剧情角色引用可以保存本地化显示名称：

```json
{
  "asset": {
    "namespace": "narrative",
    "category": "character",
    "id": "char_220_grani#5$1"
  },
  "name": "砾"
}
```

`name` 属于这一次剧情引用，不是资源 ID 或资源的全局名称。同一资源在其它剧情引用中可以使用不同名称。

剧情音频引用可以增加 `usage: "music"` 或 `usage: "sound"`。类别说明资源是什么，`usage` 说明这一次怎样使用它。例如，类别 `audio` 表示音频资源，`usage: "music"` 表示把它作为背景音乐播放。没有额外信息时直接使用通用资源引用，不添加空字段。

| 名词 | 额外信息 | 前端实例 |
| --- | --- | --- |
| 剧情引用 / Story Reference | 角色引用可保存名称；音频引用可保存 `music` 或 `sound` 用途。 | 剧情页按六类叙事资源展示引用。 |
| 合集引用 / Collection Reference | 可保存入口视频等直接引用的用途。 | 乐部页或剧情组页的入口媒体。 |
| 画廊引用 / Gallery Reference | 保存画廊成员 ID 和目标叙事资源身份；数组顺序表示组内顺序。 | 画廊查看器在同一个资源组内切换成员。 |
| 素材引用 / Material Reference | 保存成品图片使用的素材身份；数组顺序表示合成顺序。 | 图片详情页列出生成该图片所用的素材。 |

## 资源目录 / Asset Catalogs

资源目录读取一个命名空间中的资源，并为每个资源显示一张卡片或一行摘要。目录不保存资源引用，也不改变资源身份。

当前的展示资源目录包含：

- 页面 `/:locale/assets/presentation`
- 列表接口 `GET /api/:locale/assets/presentation`
- 类别、格式和引用状态筛选
- 缩略图或媒体占位、ID、尺寸或时长、引用数量
- 指向 `/:locale/assets/presentation/:asset-category/:asset-id` 的详情链接

## 六类叙事资源 / Narrative Assets

`NarrativeAsset` 是六类叙事资源的公共联合模型。调用方可以直接读取公共字段，再按 `format` 区分 `ImageAsset`、`VideoAsset` 和 `AudioAsset`。

| 名词 | 类别 / Category | 格式 / Format | 特有元数据 |
| --- | --- | --- | --- |
| 插画 / Illustration | `illustration` | `image` | 宽、高、缩略图、素材引用。 |
| 背景 / Background | `background` | `image` | 宽、高、缩略图、素材引用。 |
| 物件 / Item | `item` | `image` | 宽、高、缩略图、素材引用。 |
| 角色 / Character | `character` | `image` | 宽、高、缩略图、素材引用、角色差分。 |
| 视频 / Video | `video` | `video` | 宽、高、帧率、帧数、时长。 |
| 音频 / Audio | `audio` | `audio` | 采样率、时长。 |

## 曲谱层级 / Score Hierarchy

| 名词 | 定义 | 网址或前端实例 |
| --- | --- | --- |
| 曲谱 / Score | 曲谱层级的根，包含全部乐章。 | `/CN/scores` |
| 乐章 / Movement | 曲谱中的一级分组，包含按顺序排列的乐部和乐章分段。 | `/CN/scores/:movement-id` |
| 乐部 / Section | 乐章中的正式剧情集合，类型为主题曲、别传或故事集。 | `/CN/scores/:movement-id/:section-id` |
| 剧情 / Story | 对应单一剧情文本文件，标签为行动前、行动后或幕间。 | `/CN/scores/:movement-id/:section-id/:story-id` |
| 乐章分段 / Movement Divider | 乐章顺序中的非剧情分隔项，可引用图标和背景视频，不是乐部。 | 显示在乐章页的两个乐部之间。 |
| 展示资源 / Presentation Asset | 命名空间为 `presentation` 的游戏界面图片或视频。 | 乐章图标、乐部主视觉和乐章分段视频。 |
| 展示资源目录 / Presentation Asset Catalog | 浏览全部展示资源，并查看它们的反向引用。 | `/CN/assets/presentation`。 |

## 档案层级 / Archive Hierarchy

| 名词 | 定义 | 网址示例 / URL Example |
| --- | --- | --- |
| 档案 / Archive | 非曲谱剧情层级的根。 | `/CN/archives` |
| 档案类别 / Archive Category | 活动、干员密录、集成战略、生息演算或其他。 | `/CN/archives/:archive-category` |
| 剧情组 / Archive Group | 档案类别下的一组剧情，与乐部承担相同领域职责。 | `/CN/archives/:archive-category/:archive-group-id` |
| 档案剧情 / Archive Story | 剧情组中的单一剧情文本。 | `/CN/archives/:archive-category/:archive-group-id/:story-id` |

## 画廊 / Galleries

| 名词 | 定义 | 网址示例 / URL Example |
| --- | --- | --- |
| 画廊 / Gallery | 归属于一个乐部或剧情组的结构化展示元数据。画廊包含资源组，不是图片素材。 | `/CN/galleries/:gallery-id` |
| 资源组 / Gallery Group | 共享一个标题和介绍的一组画廊引用。 | `/CN/galleries/:gallery-id/groups/:gallery-group-id` |
| 画廊引用 / Gallery Reference | 资源组中的成员关系。它保存画廊成员 ID 和目标叙事资源身份，不是新的资源。 | `/CN/galleries/:gallery-id/groups/:gallery-group-id/:gallery-reference-id` |

## 图片素材 / Image Materials

| 名词 | 定义 | 前端实例 |
| --- | --- | --- |
| 成品图片 / Final Image Asset | 格式为 `image` 的叙事资源。它可能由阿尔法混合、角色差分组合或面板拼接生成。 | 图片详情页显示图片、元数据和素材引用。 |
| 素材 / Material Asset | 命名空间为 `material` 的输入图片。它有独立资源身份，并通过素材引用被成品图片引用。 | `/CN/assets/material/:asset-category/:asset-id` |
| 素材类型 / Material Type | 素材的生成用途，不参与资源身份。取值为 `character` 或 `panel`。 | 素材详情页显示类型。 |
| 角色素材 / Character Material | 用于组合角色差分的素材，可记录角色基础 ID、部位和差分。 | 角色成品图片的素材列表。 |
| 拼图面板 / Panel Material | 用于拼接成品图片的单块素材。`panel` 是素材类型，不是资源 ID。 | `panel_source` 可被成品图片 `cg/part` 引用。 |
| 角色差分 / Character Variant | 与当前角色资源共享角色基础 ID 的其他成品图片。 | 角色详情页的同角色差分。 |
