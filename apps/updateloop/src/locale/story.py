"""Parse localized stories and the picture and character directives they contain."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from ..domain import StoryArtReference, StoryGroupRecord, StoryRecord, StoryTag

_DATA_ROOT = Path("assets/torappu/dynamicassets/gamedata")
_INCOMPLETE_UPSTREAM_LOGGER = logging.getLogger("arkwaifu_updateloop.incomplete_upstream")
_DIRECTIVE = re.compile(
    r"\[(?P<command>\w+)(?:\((?P<params>.*?)\)\s*)?]"
    r"""|\[name\s*=\s*(?P<quote>["'])(?P<speaker>.*?)(?P=quote)"""
    r"(?:\s*,\s*(?P<speaker_params>[^]\r\n]*))?]",
    re.IGNORECASE,
)
_CHARACTER_ID = re.compile(r"^(.*?)(?:#(\d+))?(?:\$(\d+))?$")
_GROUP_TYPES = {
    "MAIN_STORY": "main_story",
    "ACTIVITY_STORY": "major_event",
    "MINI_STORY": "minor_event",
    # Every current NONE group is linked from handbookAvgList and is therefore
    # an Operator Record, rather than an unspecified catch-all category.
    "NONE": "operator_record",
}
_TAGS = {
    "行动前": "before",
    "行動前": "before",
    "Before Operation": "before",
    "戦闘前": "before",
    "작전 전": "before",
    "行动后": "after",
    "行動後": "after",
    "After Operation": "after",
    "戦闘後": "after",
    "작전 후": "after",
    "幕间": "interlude",
    "Interlude": "interlude",
    "幕間": "interlude",
    "브릿지": "interlude",
}


@dataclass(frozen=True, slots=True)
class Directive:
    """Represent one bracketed story command and its string parameters."""

    name: str
    params: dict[str, str]


def parse_story_groups(root: Path) -> tuple[StoryGroupRecord, ...]:
    """Parse every story script into its semantic or fallback directory group."""
    table = _read_json(root / _DATA_ROOT / "excel/story_review_table.json")
    metadata = _picture_metadata(root)
    variables = _story_variables(root)
    groups = []
    claimed_paths: set[str] = set()
    for raw_group_id, raw_group in _mapping(table).items():
        group_id = (_text(_at(raw_group, "id")) or raw_group_id).lower()
        raw_type = _text(_at(raw_group, "actType"))
        try:
            group_type = _GROUP_TYPES[raw_type]
        except KeyError as error:
            raise ValueError(f"unknown story group type: {raw_type!r}") from error

        stories = []
        for raw_story in _values(_at(raw_group, "infoUnlockDatas")):
            story_id = _text(_at(raw_story, "storyId")).lower()
            tag_text = _text(_at(raw_story, "avgTag"))
            try:
                tag = _TAGS[tag_text]
            except KeyError as error:
                raise ValueError(f"unknown story tag: {tag_text!r}") from error

            info_name = _text(_at(raw_story, "storyInfo"))
            story_path = _story_key(_text(_at(raw_story, "storyTxt")))
            claimed_paths.add(story_path)
            info_path = _game_data_path(root, f"story/[uc]{info_name.lower()}.txt")
            info = info_path.read_text(encoding="utf-8") if info_path.exists() else ""
            stories.append(
                _story_record(
                    id=story_id,
                    group_id=group_id,
                    tag=tag,
                    tag_text=tag_text,
                    code=_text(_at(raw_story, "storyCode")),
                    name=_text(_at(raw_story, "storyName")),
                    info=info,
                    path=_story_path(root, story_path),
                    story_path=story_path,
                    metadata=metadata,
                    variables=variables,
                )
            )
        groups.append(
            StoryGroupRecord(
                id=group_id,
                name=_text(_at(raw_group, "name")),
                group_type=group_type,
                stories=tuple(stories),
            )
        )
    groups.extend(_integrated_strategies_groups(root, metadata, variables, claimed_paths))
    groups.extend(_reclamation_groups(root, metadata, variables, claimed_paths))
    groups.extend(_other_story_groups(root, metadata, variables, claimed_paths))
    return tuple(groups)


def _integrated_strategies_groups(
    root: Path,
    metadata: dict[str, tuple[str, str]],
    variables: Mapping[str, str],
    claimed_paths: set[str],
) -> tuple[StoryGroupRecord, ...]:
    """Build one group per 集成战略 theme from its official ending catalog."""

    table = _read_json(root / _DATA_ROOT / "excel/roguelike_topic_table.json")
    topics = _mapping(_at(table, "topics"))
    details = _mapping(_at(table, "details"))
    review_meta = _read_json(root / _DATA_ROOT / "excel/story_review_meta_table.json")
    story_root = root / _DATA_ROOT / "story"

    # Monthly-squad scripts are chat logs with no indexed AVG artwork. Claim
    # their catalog paths so removing that category does not republish them as
    # unclassified story files.
    for detail in details.values():
        chats = _mapping(_at(detail, "archiveComp", "chat", "chat"))
        for squad in _values(_at(detail, "monthSquad")):
            chat = chats.get(_text(_at(squad, "chatId")))
            for item in _values(_at(chat, "chatItemList")):
                raw_path = _text(_at(item, "chatStoryId"))
                if raw_path:
                    claimed_paths.add(_story_key(raw_path))

    groups = []
    ordered_topics = sorted(
        topics.items(), key=lambda item: (_integer(_at(item[1], "sort")), item[0])
    )
    for raw_topic_id, raw_topic in ordered_topics:
        topic_id = (_text(_at(raw_topic, "id")) or raw_topic_id).lower()
        detail = _mapping(details.get(raw_topic_id))
        endings = _integrated_strategies_endings(topic_id, detail, review_meta)
        group_id = f"integrated_strategies:{topic_id}"
        stories = []
        for story_path, code, name, info in endings:
            if story_path in claimed_paths:
                continue
            claimed_paths.add(story_path)
            stories.append(
                _story_record(
                    id=_path_id("integrated_strategies", story_path),
                    group_id=group_id,
                    tag="interlude",
                    tag_text="",
                    code=code,
                    name=name,
                    info=info,
                    path=_story_path(root, story_path),
                    story_path=story_path,
                    metadata=metadata,
                    variables=variables,
                )
            )
        # Each theme directory also contains opening, tutorial, and preload
        # helpers. They support the official ending AVGs but are not separate
        # stories, so reserve the whole directory from the literal fallback.
        for directory in {PurePosixPath(item[0]).parent for item in endings}:
            source_directory = story_root.joinpath(*directory.parts)
            if source_directory.is_dir():
                claimed_paths.update(
                    _story_key(path.relative_to(story_root).as_posix())
                    for path in source_directory.rglob("*.txt")
                )
        if stories:
            groups.append(
                StoryGroupRecord(
                    id=group_id,
                    name=_text(_at(raw_topic, "name")) or topic_id,
                    group_type="integrated_strategies",
                    stories=tuple(stories),
                )
            )
    return tuple(groups)


def _integrated_strategies_endings(
    topic_id: str,
    detail: Mapping[str, Any],
    review_meta: Any,
) -> tuple[tuple[str, str, str, str], ...]:
    """Return ordered official ending AVGs for one 集成战略 theme."""

    if topic_id == "rogue_1":
        endings = []
        for raw in _values(_at(review_meta, "actArchiveResData", "avgs")):
            raw_path = _text(_at(raw, "contentPath"))
            if not raw_path:
                continue
            path = _story_key(raw_path)
            if not path.startswith("obt/roguelike/ro1/level_rogue1_ending_"):
                continue
            endings.append(
                (
                    path,
                    _text(_at(raw, "id")),
                    _text(_at(raw, "desc")),
                    _text(_at(raw, "rawBrief")),
                )
            )
        return tuple(sorted(endings))

    endbooks = _mapping(_at(detail, "archiveComp", "endbook", "endbook"))
    endings = []
    for raw_id, raw in sorted(
        endbooks.items(),
        key=lambda item: (_integer(_at(item[1], "sortId")), item[0]),
    ):
        raw_path = _text(_at(raw, "avgId"))
        if not raw_path:
            continue
        path = _story_key(raw_path)
        endings.append(
            (
                path,
                _text(_at(raw, "endingId")) or raw_id,
                _text(_at(raw, "title")),
                "",
            )
        )
    return tuple(endings)


def _reclamation_groups(
    root: Path,
    metadata: dict[str, tuple[str, str]],
    variables: Mapping[str, str],
    claimed_paths: set[str],
) -> tuple[StoryGroupRecord, ...]:
    """Build one 生息演算 group per topic and leave its guides to ``others``."""

    table = _read_json(root / _DATA_ROOT / "excel/sandbox_perm_table.json")
    basic_info = _mapping(_at(table, "basicInfo"))
    details = _mapping(_at(table, "detail"))
    story_root = root / _DATA_ROOT / "story"
    groups = []
    ordered_topics = sorted(
        basic_info.items(), key=lambda item: (_integer(_at(item[1], "sortId")), item[0])
    )
    for raw_topic_id, raw_topic in ordered_topics:
        topic_id = (_text(_at(raw_topic, "topicId")) or raw_topic_id).lower()
        directory = story_root / "obt" / "sandboxperm" / topic_id
        if not directory.is_dir():
            continue
        template = _text(_at(raw_topic, "topicTemplate"))
        detail = _mapping(_at(details, template, topic_id))
        names, descriptions = _reclamation_metadata(detail)
        paths = []
        for path in directory.rglob("*.txt"):
            relative = path.relative_to(story_root)
            lowered_parts = tuple(part.lower() for part in relative.parts)
            if "traininglevel" in lowered_parts or "uiavg" in lowered_parts:
                continue
            if path.name.lower() == f"{topic_id}_challenge_mode_guide.txt":
                continue
            paths.append(path)
        stories = []
        group_id = f"reclamation_algorithm:{topic_id}"
        for path in sorted(paths, key=lambda value: value.as_posix().lower()):
            story_path = _story_key(path.relative_to(story_root).as_posix())
            if story_path in claimed_paths:
                continue
            claimed_paths.add(story_path)
            story = _story_record(
                id=_path_id("reclamation_algorithm", story_path),
                group_id=group_id,
                tag="interlude",
                tag_text="",
                code="",
                name=names.get(story_path, path.stem),
                info=descriptions.get(story_path, ""),
                path=path,
                story_path=story_path,
                metadata=metadata,
                variables=variables,
            )
            if story.art_references:
                stories.append(story)
        if stories:
            groups.append(
                StoryGroupRecord(
                    id=group_id,
                    name=_text(_at(raw_topic, "topicName")) or topic_id,
                    group_type="reclamation_algorithm",
                    stories=tuple(stories),
                )
            )
    return tuple(groups)


def _reclamation_metadata(detail: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    names: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    quests = sorted(
        _mapping(_at(detail, "archiveQuestData")).values(),
        key=lambda value: _integer(_at(value, "sortId")),
    )
    for quest in quests:
        description = _text(_at(quest, "desc"))
        for raw_story in _values(_at(quest, "avgDataList")):
            story_path = _story_key(_text(_at(raw_story, "avgId")))
            names[story_path] = _text(_at(raw_story, "avgName"))
            descriptions[story_path] = description
    return names, descriptions


def _other_story_groups(
    root: Path,
    metadata: dict[str, tuple[str, str]],
    variables: Mapping[str, str],
    claimed_paths: set[str],
) -> tuple[StoryGroupRecord, ...]:
    """Expose every remaining story script, grouped only by its source directory."""

    story_root = root / _DATA_ROOT / "story"
    grouped: dict[str, list[tuple[Path, str]]] = {}
    if not story_root.is_dir():
        return ()
    for path in sorted(story_root.rglob("*.txt"), key=lambda value: value.as_posix().lower()):
        relative = path.relative_to(story_root)
        if relative.parts and relative.parts[0].lower().startswith("[uc]"):
            continue
        story_path = _story_key(relative.as_posix())
        if story_path in claimed_paths:
            continue
        directory = PurePosixPath(story_path).parent.as_posix()
        grouped.setdefault(directory, []).append((path, story_path))

    groups = []
    for directory, paths in grouped.items():
        group_id = _path_id("others", directory if directory != "." else "root")
        stories = tuple(
            _story_record(
                id=_path_id("others", story_path),
                group_id=group_id,
                tag="interlude",
                tag_text="",
                code="",
                name=path.stem,
                info="",
                path=path,
                story_path=story_path,
                metadata=metadata,
                variables=variables,
            )
            for path, story_path in paths
        )
        groups.append(
            StoryGroupRecord(
                id=group_id,
                name=directory,
                group_type="others",
                stories=stories,
            )
        )
    return tuple(groups)


def _story_record(
    *,
    id: str,
    group_id: str,
    tag: StoryTag,
    tag_text: str,
    code: str,
    name: str,
    info: str,
    path: Path,
    story_path: str,
    metadata: dict[str, tuple[str, str]],
    variables: Mapping[str, str],
) -> StoryRecord:
    if path.is_file():
        directives = parse_directives(path.read_text(encoding="utf-8"))
    else:
        _INCOMPLETE_UPSTREAM_LOGGER.warning(
            "story text is missing; continuing without art references story_id=%s path=%s",
            id,
            f"gamedata/story/{story_path}.txt",
        )
        directives = ()
    return StoryRecord(
        id=id,
        group_id=group_id,
        tag=tag,
        tag_text=tag_text,
        code=code,
        name=name,
        info=info,
        art_references=(*_pictures(directives, metadata), *_characters(directives, variables)),
    )


def _story_key(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe story path: {value}")
    if path.suffix.lower() == ".txt":
        path = path.with_suffix("")
    return path.as_posix().lower()


def _story_path(root: Path, story_path: str) -> Path:
    return _game_data_path(root, f"story/{story_path}.txt")


def _path_id(prefix: str, story_path: str) -> str:
    return f"{prefix}:{story_path.replace('/', ':')}"


def parse_directives(raw: str) -> tuple[Directive, ...]:
    """Parse all bracketed commands from one story text file."""

    directives = []
    for match in _DIRECTIVE.finditer(raw):
        explicit_name = match.group("speaker")
        if explicit_name is not None:
            params = _parse_params(match.group("speaker_params") or "")
            params["name"] = explicit_name
            directives.append(Directive("", params))
        else:
            directives.append(
                Directive(
                    match.group("command").lower(),
                    _parse_params(match.group("params") or ""),
                )
            )
    return tuple(directives)


def normalize_character_id(identifier: str) -> str:
    """Return a lower-case ``base#face$body`` identifier with default variants."""

    # Normalize harmless upstream spelling differences so every reference to
    # one sprite has the same database key. GameData occasionally pads numeric
    # variants or inserts whitespace beside their separators; neither selects
    # a different face or body.
    identifier = "".join(identifier.split())
    # A leading ``$name`` is a story-variable reference, whereas only a
    # trailing ``$<digits>`` selects a body. Variable references must first be
    # resolved against the snapshot's story_variables.json by the caller.
    if not identifier or identifier.startswith("$") or identifier.lower() == "char_empty":
        return ""
    match = _CHARACTER_ID.fullmatch(identifier)
    if match is None:
        return ""
    base, face, body = match.groups()
    face = str(int(face)) if face is not None else "1"
    body = str(int(body)) if body is not None else "1"
    return f"{base}#{face}${body}".lower()


def _pictures(
    directives: tuple[Directive, ...],
    metadata: dict[str, tuple[str, str]],
) -> tuple[StoryArtReference, ...]:
    pictures = []

    def add(identifier: str, category: str) -> None:
        art_id = identifier.lower()
        if not art_id:
            return
        title, subtitle = metadata.get(art_id, ("", ""))
        pictures.append(
            StoryArtReference(
                art_id=art_id,
                kind="picture",
                category=category,
                title=title,
                subtitle=subtitle,
            )
        )

    for directive in directives:
        if directive.name == "image":
            add(directive.params.get("image", ""), "image")
        elif directive.name == "background":
            add(directive.params.get("image", ""), "background")
        elif directive.name in {"largebg", "gridbg"}:
            for identifier in directive.params.get("imagegroup", "").split("/"):
                add(identifier, "background")
        elif directive.name == "showitem":
            add(directive.params.get("image", ""), "item")
    return tuple(pictures)


def _characters(
    directives: tuple[Directive, ...],
    variables: Mapping[str, str],
) -> tuple[StoryArtReference, ...]:
    """Reconstruct character appearances from slot, focus, and dialog state.

    References preserve first appearance order. Spoken names attach to the
    currently focused slot and are deduplicated only when the final record is
    produced.
    """

    characters: dict[str, str] = {}
    spotlight = ""
    history: list[str] = []
    names: dict[str, list[str]] = {}

    def take(slot: str, identifier: str) -> None:
        if identifier:
            characters[slot] = identifier
            history.append(identifier)
        else:
            characters.pop(slot, None)

    def focus(slot: str) -> str:
        if slot:
            return slot
        if len(characters) == 1:
            return next(iter(characters))
        return ""

    for directive in directives:
        if directive.name == "":
            protagonist = characters.get(spotlight, "")
            names.setdefault(protagonist, []).append(directive.params.get("name", ""))
        elif directive.name == "character":
            take("1", _resolve_character_id(directive.params.get("name", ""), variables))
            take("2", _resolve_character_id(directive.params.get("name2", ""), variables))
            spotlight = focus(directive.params.get("focus", ""))
        elif directive.name == "charslot":
            slot = directive.params.get("slot", "")
            raw_identifier = directive.params.get("name", "")
            clears_slot = raw_identifier.strip().lower() == "char_empty"
            if not slot:
                # Bare charslot directives clear the scene. A nonempty unknown
                # name such as ``left`` is a position-control token, not art.
                if not raw_identifier or clears_slot:
                    spotlight = ""
                    characters.clear()
                continue
            if clears_slot:
                take(slot, "")
                requested_focus = directive.params.get("focus", "")
                if requested_focus:
                    spotlight = focus(requested_focus)
                elif spotlight == slot:
                    spotlight = ""
                continue
            identifier = _resolve_character_id(raw_identifier, variables)
            if identifier:
                take(slot, identifier)
                spotlight = focus(directive.params.get("focus", ""))
            elif directive.params.get("focus", ""):
                spotlight = focus(directive.params["focus"])
        elif directive.name == "dialog":
            spotlight = ""
            characters.clear()

    return tuple(
        StoryArtReference(
            art_id=identifier,
            kind="character",
            category="character",
            names=tuple(dict.fromkeys(name for name in names.get(identifier, []) if name)),
        )
        for identifier in dict.fromkeys(history)
    )


def _resolve_character_id(identifier: str, variables: Mapping[str, str]) -> str:
    """Resolve a story variable, if present, and return its concrete sprite ID."""

    candidate = identifier.strip()
    if candidate.startswith("$"):
        candidate = variables.get(candidate[1:].lower(), "")
    return normalize_character_id(candidate)


def _story_variables(root: Path) -> dict[str, str]:
    """Read string story variables used by character directives in this snapshot."""

    path = root / _DATA_ROOT / "story/story_variables.json"
    if not path.is_file():
        return {}
    return {
        key.lower(): value
        for key, value in _mapping(_read_json(path)).items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _picture_metadata(root: Path) -> dict[str, tuple[str, str]]:
    path = root / _DATA_ROOT / "excel/story_review_meta_table.json"
    data = _read_json(path)
    result = {}
    for raw in _values(_at(data, "actArchiveResData", "pics")):
        identifier = _text(_at(raw, "assetPath")).lower()
        if identifier:
            result[identifier] = (
                _text(_at(raw, "desc")),
                _text(_at(raw, "picDescription")),
            )
    return result


def _parse_params(raw: str) -> dict[str, str]:
    params = {}
    for token in _split_tokens(raw):
        key, separator, value = token.partition("=")
        params[key.strip().lower()] = value.strip().strip('"') if separator else ""
    return params


def _split_tokens(raw: str) -> tuple[str, ...]:
    """Split comma-separated parameters while preserving commas inside quotes."""

    if not raw:
        return ()
    tokens = []
    start = 0
    quoted = False
    for index, character in enumerate(raw):
        if character == '"':
            quoted = not quoted
        elif character == "," and not quoted:
            tokens.append(raw[start:index])
            start = index + 1
    tokens.append(raw[start:])
    return tuple(tokens)


def _game_data_path(root: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts:
        raise ValueError(f"unsafe game-data path: {relative}")
    return root / _DATA_ROOT.joinpath(*posix.parts)


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _at(value: Any, *path: str) -> Any:
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _values(value: Any) -> tuple[Any, ...]:
    if isinstance(value, dict):
        return tuple(value.values())
    if isinstance(value, list):
        return tuple(value)
    return ()


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _integer(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
