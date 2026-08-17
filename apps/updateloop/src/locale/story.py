"""Parse localized stories and the picture and character directives they contain."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from ..domain import (
    ArchiveGroup,
    Movement,
    MovementSection,
    StoryArtReference,
    StoryMediaKind,
    StoryMediaReference,
    StoryRecord,
    StoryTag,
)
from ..local_path import resolve_local_path, safe_relative_path
from .score import parse_score

_DATA_ROOT = Path("assets/torappu/dynamicassets/gamedata")
_INCOMPLETE_UPSTREAM_LOGGER = logging.getLogger("arkwaifu_updateloop.incomplete_upstream")
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
    source_name: str = ""


DirectiveAction = Literal["art", "characters", "media", "discard", "speaker"]


@dataclass(frozen=True, slots=True)
class DirectiveSpec:
    """Declare one known story directive and its accepted parameter shape.

    A shape is the set of parameter names the game-data parser has observed
    for this directive. Optional parameters may be omitted in any combination;
    a new parameter name is the actionable change that produces a warning.
    """

    name: str
    action: DirectiveAction
    parameters: frozenset[str]
    canonical_name: str | None = None
    resource_indexed: bool = False


def _shape(*parameters: str) -> frozenset[str]:
    return frozenset(parameters)


_HANDLED_DIRECTIVE_ACTIONS: dict[str, DirectiveAction] = {
    "name": "speaker",
    "image": "art",
    "background": "art",
    "backgroundtween": "art",
    "bgeffect": "art",
    "largebgtween": "art",
    "largebg": "art",
    "gridbg": "art",
    "verticalbg": "art",
    "cgitem": "art",
    "hidecgitem": "art",
    "showitem": "art",
    "imgeffect": "art",
    "imagerotate": "art",
    "imagetween": "art",
    "avgdisplay": "art",
    "character": "characters",
    "charslot": "characters",
    "dialog": "characters",
    "playsound": "media",
    "voicewithin": "media",
    "playmusic": "media",
    "video": "media",
}


# This is intentionally a data declaration instead of a fall-through parser.
# The parameter sets are the union of the current CN/EN/JP/KR/TW snapshots;
# optional parameters are not required to appear in every invocation.
_KNOWN_DIRECTIVE_PARAMETER_SHAPES: dict[str, frozenset[str]] = {
    "name": _shape(
        "avatarid", "delay", "isavatarleft", "isavatarright", "name", "offsetx", "offsety"
    ),
    "activity.resettoentry": _shape(),
    "addfavor": _shape("trapid", "val"),
    "additem": _shape("itemcount", "itemid"),
    "animtext": _shape("block", "id", "name", "pos", "style"),
    "animtextclean": _shape(),
    "arkodc_ensure_task_hud_stable": _shape(),
    "assemble": _shape(),
    "autochess.focusband": _shape(),
    "autochess.focusstageinfo": _shape("itemtype"),
    "autochess.shopdetailfocus": _shape("type"),
    "autochess.shoplistfocusdiychess": _shape(),
    "avatarid": _shape("isavatarright"),
    "avgdisplay": _shape(
        "afrom",
        "ato",
        "block",
        "duration",
        "entryfrom",
        "entryto",
        "id",
        "isblock",
        "layer",
        "name",
        "scalex",
        "scalexto",
        "scaley",
        "scaleyto",
        "slot",
        "style",
        "x",
        "xto",
        "y",
        "yto",
    ),
    "background": _shape(
        "block",
        "duration",
        "fadetime",
        "height",
        "image",
        "isblock",
        "screenadapt",
        "tiled",
        "time",
        "width",
        "x",
        "xscale",
        "xscaleto",
        "xsclae",
        "y",
        "yfrom",
        "ypos",
        "yscale",
        "yscalefrom",
        "yscaleto",
        "ysclae",
    ),
    "backgroundtween": _shape(
        "block",
        "duration",
        "ease",
        "else",
        "fadetime",
        "image",
        "isblock",
        "screenadapt",
        "x",
        "xfrom",
        "xscale",
        "xscalefrom",
        "xscaleto",
        "xto",
        "y",
        "yfrom",
        "yscale",
        "yscalefrom",
        "yscaleto",
        "yto",
    ),
    "battle.autochessonlyallow": _shape("bindkey", "hint", "reqconditionkey"),
    "battle.autochessonlydisable": _shape("bindkey", "reqconditionkey"),
    "battle.delay": _shape("time"),
    "battle.elay": _shape("time"),
    "battle.ensuremincost": _shape("cost"),
    "battle.ensureminsp": _shape("charid", "sp"),
    "battle.lockautochesshud": _shape(),
    "battle.lockfunction": _shape("mask"),
    "battle.pause": _shape("pause"),
    "battle.setdragoperationlock": _shape("islocked"),
    "battle.switchtodefaultuistate": _shape(),
    "battle.unlockautochesshud": _shape(),
    "battle.unlockfunction": _shape("mask"),
    "bgeffect": _shape(
        "block",
        "delay",
        "duration",
        "fade",
        "fadetime",
        "flip",
        "layer",
        "movetime",
        "name",
        "x",
        "xto",
        "y",
        "yto",
    ),
    "blocker": _shape(
        "a",
        "afrom",
        "b",
        "bfrom",
        "block",
        "duration",
        "ease",
        "fadetime",
        "g",
        "gfrom",
        "image",
        "initr",
        "inverse",
        "isblock",
        "r",
        "rfrom",
        "style",
    ),
    "building.ensureoperationmode": _shape("mode"),
    "building.focusbroom": _shape("needselect", "roomid"),
    "building.focusonprivateowner": _shape(),
    "building.privatereturn": _shape(),
    "cameraeffect": _shape(
        "amount", "block", "effect", "fadetime", "from", "initamount", "keep", "to"
    ),
    "camerafocusto": _shape("enemyaliasid", "id", "offsetx", "offsety", "scale", "time"),
    "camerascale": _shape("scale", "time"),
    "camerashake": _shape(
        "block",
        "delay",
        "duration",
        "fadeout",
        "fadetime",
        "focus",
        "isblock",
        "randomness",
        "stop",
        "strength",
        "strengthx",
        "strengthy",
        "strengthz",
        "vibrato",
        "xstrength",
        "ystrength",
    ),
    "campaign.focuszone": _shape("waitforsignal", "zoneid"),
    "campaign.registerzonebtn": _shape("zoneid"),
    "carving.focusbuycard": _shape("position"),
    "carving.selectcardslot": _shape(),
    "carving.selecthandcard": _shape("cardid"),
    "cgitem": _shape(
        "aduration",
        "afrom",
        "ato",
        "block",
        "duration",
        "ease",
        "image",
        "layer",
        "pdelay",
        "pduration",
        "pfrom",
        "pto",
        "rduration",
        "rfrom",
        "rto",
        "sduration",
        "sfrom",
        "sto",
        "style",
    ),
    "chaa": _shape(),
    "character": _shape(
        "blackend",
        "blackend1",
        "blackend2",
        "blackstart",
        "blackstart1",
        "blackstart2",
        "blo",
        "block",
        "blockl",
        "blok",
        "delay",
        "duration",
        "enter",
        "enter2",
        "exit2",
        "fadeitme",
        "fadeout",
        "fadetiem",
        "fadetim",
        "fadetime",
        "fadtime",
        "faetime",
        "fatetime",
        "fedetime",
        "focus",
        "foucs",
        "fpcus",
        "isblock",
        "name",
        "name1",
        "name2",
        "nameage",
        "offsetx",
        "offsety",
        "screenadapt",
        "slot",
        "time",
    ),
    "characteraction": _shape(
        "block",
        "delay",
        "direction",
        "duration",
        "fadetime",
        "isblock",
        "loop",
        "name",
        "power",
        "pwoer",
        "scale",
        "time",
        "times",
        "type",
        "xpos",
        "y",
        "ypos",
    ),
    "charactercutin": _shape(
        "block",
        "fadestyle",
        "fadetime",
        "name",
        "offsetx",
        "povx",
        "style",
        "widgetid",
        "width",
    ),
    "charselect.applysortfilter": _shape("professionfilter", "sorttype"),
    "charslot": _shape(
        "action",
        "aduration",
        "afrom",
        "ato",
        "bend",
        "block",
        "blocker",
        "bstart",
        "bstrart",
        "charslot",
        "delay",
        "dfocus",
        "direction",
        "duraiton",
        "duratin",
        "duratio",
        "duration",
        "ease",
        "end",
        "fadetime",
        "focus",
        "foucs",
        "glitch",
        "grad",
        "isblock",
        "isblocke",
        "iscopy",
        "layer",
        "matname",
        "name",
        "ocus",
        "pfrom",
        "poasfrom",
        "posform",
        "posfrom",
        "posto",
        "poszoom",
        "power",
        "random",
        "scale",
        "slot",
        "time",
        "times",
        "type",
    ),
    "charslsot": _shape(),
    "combat": _shape(),
    "condition": _shape(
        "containseq", "itemid", "key", "references", "riftid", "trapid", "val", "value"
    ),
    "consumeguideonstoryend": _shape("showanyway", "subsignal", "target"),
    "cooperatebattle.camerafocusto": _shape("offsetx", "offsety", "scale", "time"),
    "cooperatebattle.lockcamera": _shape("enable"),
    "createeffect": _shape("enemyaliasid", "id", "key"),
    "crisisv2.focusslot": _shape("slottype"),
    "crisisv2.hidepreview": _shape(),
    "crisisv2.resettoentry": _shape(),
    "crisisv2.switchmap": _shape("maptype"),
    "criteria": _shape(),
    "crystal": _shape(),
    "crystalline": _shape(),
    "crystallization": _shape(),
    "curtain": _shape(
        "a",
        "afrom",
        "ato",
        "block",
        "direction",
        "duration",
        "fadetime",
        "fillfrom",
        "fillto",
        "grad",
        "isblock",
    ),
    "dalay": _shape("time"),
    "daley": _shape("time"),
    "dealy": _shape("time"),
    "decision": _shape(
        "option1",
        "option2",
        "option3",
        "option4",
        "options",
        "value1",
        "value2",
        "value3",
        "value4",
        "values",
    ),
    "delat": _shape("time"),
    "delau": _shape("time"),
    "delay": _shape(
        "black",
        "block",
        "fadetime",
        "t",
        "time",
        "times",
        "timr",
        "timw",
        "tinme",
        "title_test",
        "yime",
    ),
    "delay9ti": _shape(),
    "delayt": _shape("time"),
    "deliveritem": _shape("itemid", "value"),
    "delya": _shape("time"),
    "dialo": _shape(),
    "dialog": _shape("block", "delay", "fadetime", "head", "style", "time"),
    "dialogs": _shape(),
    "div": _shape("style"),
    "duration": _shape(),
    "effect": _shape(
        "delay",
        "flip",
        "layer",
        "movetime",
        "name",
        "rox",
        "roy",
        "roz",
        "x",
        "xto",
        "y",
        "ypos",
        "yscale",
        "z",
    ),
    "emoji": _shape("emoji", "target"),
    "end": _shape(),
    "entertouristmode": _shape("timelinename"),
    "executeactionarray": _shape("key", "target"),
    "fadetime": _shape(),
    "find": _shape(),
    "finisheffect": _shape("id", "key"),
    "firework.waitforcraftpagestable": _shape(),
    "focusout": _shape("block", "duration", "fadetime", "from", "id", "to", "type"),
    "focusparam": _shape("blur", "effect"),
    "foginview": _shape("id", "leftbottomx", "leftbottomy", "rightupx", "rightupy"),
    "fognotinview": _shape("id"),
    "fountain": _shape(),
    "gacha": _shape("all", "cnt", "gachapool"),
    "gotocharinfo": _shape(),
    "gotopage": _shape("dest", "initmissionpage", "stageid", "waitforsignal", "zoneid"),
    "gotostage": _shape("target"),
    "gridbg": _shape(
        "block",
        "blok",
        "fadetime",
        "imagegroup",
        "solidheight",
        "solidwidth",
        "x",
        "xscale",
        "y",
        "yscale",
    ),
    "header": _shape(
        "actid",
        "char_sort_type",
        "deny_auto_switch_scene",
        "dont_clear_gameobjectpool_onstart",
        "fit_mode",
        "is_autoable",
        "is_skippable",
        "is_tutorial",
        "is_video_only",
        "key",
        "npcid",
        "withdrawwithoutanim",
    ),
    "heart": _shape(),
    "hidecgitem": _shape("block", "fadetime", "image"),
    "hideitem": _shape("block", "fadetime"),
    "hurdle": _shape(),
    "image": _shape(
        "adetime",
        "block",
        "ease",
        "fadetime",
        "fxscale",
        "height",
        "image",
        "isblock",
        "layer",
        "screenadapt",
        "tiled",
        "time",
        "width",
        "x",
        "xfrom",
        "xpos",
        "xscale",
        "xscalefrom",
        "xscaleto",
        "xto",
        "y",
        "yfrom",
        "ypos",
        "yscale",
        "yscalefrom",
        "yscalet",
        "yscaleto",
        "yto",
    ),
    "imagerotate": _shape("angle", "block", "ease", "fadetime", "image", "inverse", "isblock"),
    "imagetween": _shape(
        "block",
        "duration",
        "ease",
        "fadetime",
        "image",
        "screenadapt",
        "tiled",
        "x",
        "xfrom",
        "xfromscale",
        "xscale",
        "xscalefrom",
        "xscaleto",
        "xto",
        "y",
        "yfrom",
        "yfromscale",
        "yscale",
        "yscalefrom",
        "yscaleto",
        "yt",
        "yto",
    ),
    "imgeffect": _shape("image", "name"),
    "inputblocker": _shape(
        "anchor",
        "battletarget",
        "black",
        "blockinput",
        "cardindex",
        "rightstart",
        "tilex",
        "tiley",
        "validheight",
        "validwidth",
        "validx",
        "validy",
    ),
    "interlock.ensuremapstatus": _shape(),
    "interlude": _shape(
        "aduration",
        "afrom",
        "ato",
        "block",
        "channel",
        "char",
        "clear",
        "direction",
        "duration",
        "fadetime",
        "isblock",
        "maskid",
        "name",
        "offset",
        "pfrom",
        "pto",
        "sduration",
        "sfrom",
        "size",
        "slot",
        "sto",
        "style",
        "switch",
        "tsduration",
        "tsfrom",
        "tsto",
        "type",
    ),
    "isavatarright": _shape(),
    "key": _shape(),
    "largebg": _shape(
        "block",
        "cggroup",
        "fadetime",
        "imagegroup",
        "solidheight",
        "solidwidth",
        "x",
        "xscale",
        "y",
        "yscale",
    ),
    "largebgtween": _shape(
        "block",
        "duration",
        "ease",
        "xfrom",
        "xscalefrom",
        "xscaleto",
        "xto",
        "yfrom",
        "yscalefrom",
        "yscaleto",
        "yto",
    ),
    "main": _shape(),
    "mixstory.focusstoryline": _shape("storylineid"),
    "move": _shape("col", "enemyaliasid", "enemyid", "row", "x", "y"),
    "multiline": _shape("delay", "end", "name"),
    "musicvolume": _shape("channel", "fadetime", "volume"),
    "musicvolune": _shape("fadetime", "volume"),
    "narration": _shape("delay", "style"),
    "objective": _shape(),
    "obtain": _shape("delay", "id"),
    "optionbranch": _shape("delay", "option0", "option1", "option2"),
    "orderrift": _shape("riftid"),
    "palysound": _shape("name", "volume"),
    "playanim": _shape(
        "anim", "charid", "dir", "enemyaliasid", "enemyid", "id", "looporidle", "noidlewhenfinish"
    ),
    "playmusic": _shape(
        "block",
        "crossfade",
        "crosstime",
        "daley",
        "delay",
        "fadetime",
        "intro",
        "key",
        "volu7me",
        "volume",
    ),
    "playsound": _shape(
        "block",
        "channel",
        "crossfade",
        "crosstime",
        "delai",
        "delay",
        "fadetime",
        "key",
        "loop",
        "volum",
        "volume",
        "voluyme",
        "y",
    ),
    "popupdialog": _shape(
        "anchor",
        "animstyle",
        "black",
        "dialoghead",
        "dialogx",
        "dialogy",
        "focusheight",
        "focusstyle",
        "focuswidth",
        "focusx",
        "focusy",
        "protecttime",
    ),
    "predicate": _shape("references", "selectablecondition", "visiblecondition"),
    "prts": _shape(),
    "resetcamera": _shape("time", "times"),
    "rotating": _shape(),
    "sandbox.dungeonfocusnode": _shape("focustype"),
    "sandbox.ensuredungeonstable": _shape(),
    "sandbox.focusmodule": _shape("module"),
    "sandboxbattle.camerafocusto": _shape("offsetx", "offsety", "time"),
    "sandboxbattle.lockcamera": _shape("enable"),
    "sandboxv2.closegainitempage": _shape(),
    "sandboxv2.dungeonbacktodungeonstate": _shape(),
    "sandboxv2.dungeonfocusnode": _shape(
        "enemyrushgroupkey", "focusnodeid", "focustype", "zoomtype"
    ),
    "sandboxv2.ensuredungeonquest": _shape("isforcetutorial", "questid"),
    "sandboxv2.ensuredungeonstable": _shape(),
    "sandboxv2.opengainitempage": _shape("itemcount", "itemid"),
    "sandboxv2.settlegameandleave": _shape(),
    "sandboxv3.dungeonfocusnode": _shape("focusnodeid"),
    "sandboxv3activepredefine": _shape("alias"),
    "sandboxv3openshop": _shape(),
    "sandboxv3summontrap": _shape("charid", "dir", "ischar", "skillindex", "x", "y"),
    "save": _shape(),
    "scoring": _shape(),
    "setconditionprogress": _shape("conditionkey", "itemcount"),
    "setposition": _shape("enemyid", "x", "y"),
    "shop.switchtoptab": _shape("shoptype"),
    "showitem": _shape("fadestyle", "fadetime", "image", "offsetx", "style", "width"),
    "skipnode": _shape("mode"),
    "skiptothis": _shape(),
    "soundvolume": _shape("channel", "fadetime", "volume"),
    "spellsticker": _shape(
        "action", "alpha", "angle", "block", "id", "style", "x", "xscale", "y", "yscale"
    ),
    "spellstickerclear": _shape("block"),
    "startbattle": _shape("stageid"),
    "sticker": _shape(
        "afrom",
        "alignment",
        "ato",
        "block",
        "delay",
        "duration",
        "fadetime",
        "hidelog",
        "id",
        "multi",
        "size",
        "text",
        "width",
        "x",
        "y",
    ),
    "stickerclear": _shape(),
    "stopmucis": _shape("fadetime"),
    "stopmusic": _shape(
        "block", "crossfade", "faddetime", "fadeetime", "fadetime", "fdetime", "time"
    ),
    "stopsound": _shape(
        "channel", "duration", "fadetime", "fedatime", "isblock", "key", "time", "volume"
    ),
    "subtitle": _shape(
        "afrom",
        "alignment",
        "ato",
        "block",
        "delay",
        "duration",
        "fadetime",
        "multi",
        "size",
        "text",
        "width",
        "x",
        "y",
    ),
    "summonenemy": _shape(
        "countaskilled", "endcol", "endrow", "endx", "endy", "enemyaliasid", "enemyid", "x", "y"
    ),
    "summontrap": _shape("charid", "dir", "endx", "endy", "ischar", "x", "y"),
    "super": _shape(),
    "theater": _shape("mode"),
    "timerclear": _shape("afrom", "ato", "duration"),
    "timersticker": _shape("size", "time", "width", "x", "y"),
    "title": _shape(),
    "tutorial": _shape(
        "abortforsignal",
        "anchor",
        "animstyle",
        "battletarget",
        "black",
        "cardindex",
        "charid",
        "dialoghead",
        "dialogx",
        "dialogy",
        "endanchor",
        "endbattletarget",
        "endtilex",
        "endtiley",
        "endx",
        "endy",
        "focusheight",
        "focusstyle",
        "focuswidth",
        "focusx",
        "focusy",
        "importantclick",
        "posx",
        "posy",
        "protecttime",
        "rightstart",
        "searchbtninchildren",
        "startanchor",
        "startbattletarget",
        "startcardindex",
        "startrightstart",
        "starttilex",
        "starttiley",
        "startx",
        "starty",
        "target",
        "tilex",
        "tiley",
        "waitforsignal",
    ),
    "uioperation": _shape("enable", "item", "target"),
    "verticalbg": _shape(
        "cggroup",
        "fadetime",
        "imagegroup",
        "solidheight",
        "solidwidth",
        "x",
        "xscale",
        "y",
        "yscale",
    ),
    "video": _shape("res"),
    "voicewithin": _shape("delay", "head"),
    "warp": _shape("name"),
    "withdraw": _shape("charid", "col", "id", "row", "withoutanim"),
    "withdrawsource": _shape("without", "withoutanim"),
}


_DIRECTIVE_ALIASES = {
    "palysound": "playsound",
    "charslsot": "charslot",
    "dialo": "dialog",
    "musicvolune": "musicvolume",
    "stopmucis": "stopmusic",
    "battle.elay": "battle.delay",
    "dalay": "delay",
    "daley": "delay",
    "dealy": "delay",
    "delat": "delay",
    "delau": "delay",
    "delay9ti": "delay",
    "delayt": "delay",
    "delya": "delay",
}


def _directive_spec(name: str, parameters: frozenset[str]) -> DirectiveSpec:
    action = _HANDLED_DIRECTIVE_ACTIONS.get(name, "discard")
    return DirectiveSpec(
        name=name,
        action=action,
        parameters=parameters,
        resource_indexed=action in {"art", "characters", "media"},
    )


DIRECTIVE_SPECS: dict[str, DirectiveSpec] = {
    name: _directive_spec(name, parameters)
    for name, parameters in _KNOWN_DIRECTIVE_PARAMETER_SHAPES.items()
}
for _alias, _canonical in _DIRECTIVE_ALIASES.items():
    _alias_spec = DIRECTIVE_SPECS[_alias]
    DIRECTIVE_SPECS[_alias] = replace(
        _alias_spec,
        canonical_name=_canonical,
        action=DIRECTIVE_SPECS[_canonical].action,
        resource_indexed=False,
    )


HANDLED_DIRECTIVES = frozenset(
    name for name, spec in DIRECTIVE_SPECS.items() if spec.action != "discard"
)
DISCARDED_DIRECTIVES = frozenset(
    name for name, spec in DIRECTIVE_SPECS.items() if spec.action == "discard"
)


_DIRECTIVE_WARNING_KEYS: set[tuple[str, tuple[str, ...]]] = set()
_DIRECTIVE_LOGGER = logging.getLogger("arkwaifu_updateloop.story_parser")


def _warn_directive_once(
    source_name: str,
    shape: tuple[str, ...],
    message: str,
    *args: object,
) -> None:
    warning_key = (source_name, shape)
    if warning_key in _DIRECTIVE_WARNING_KEYS:
        return
    _DIRECTIVE_WARNING_KEYS.add(warning_key)
    _DIRECTIVE_LOGGER.warning(message, *args)


def _directive_source_name(directive: Directive) -> str:
    return directive.source_name or directive.name


def _directive_name(directive: Directive) -> str:
    source_name = _directive_source_name(directive)
    spec = DIRECTIVE_SPECS.get(source_name)
    return spec.canonical_name if spec and spec.canonical_name else source_name


def _validate_directive_shape(directive: Directive) -> None:
    """Warn once when a story introduces a new name or parameter shape."""

    source_name = _directive_source_name(directive)
    spec = DIRECTIVE_SPECS.get(source_name)
    shape = tuple(sorted(directive.params))
    if spec is None:
        _warn_directive_once(
            source_name,
            shape,
            "unknown story directive name=%s parameters=%s",
            source_name,
            shape,
        )
        return
    unknown = tuple(sorted(set(shape) - spec.parameters))
    if not unknown:
        return
    _warn_directive_once(
        source_name,
        shape,
        "unknown story directive shape name=%s unknown_parameters=%s parameters=%s",
        source_name,
        unknown,
        shape,
    )


@dataclass(frozen=True, slots=True)
class _ParsedGroup:
    id: str
    name: str
    group_type: str
    stories: tuple[StoryRecord, ...]


def parse_story_data(
    root: Path,
) -> tuple[tuple[Movement, ...], tuple[MovementSection, ...], tuple[ArchiveGroup, ...]]:
    """Parse the complete Score hierarchy and the remaining Archive groups."""

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
            _ParsedGroup(
                id=group_id,
                name=_text(_at(raw_group, "name")),
                group_type=group_type,
                stories=tuple(stories),
            )
        )
    groups.extend(_integrated_strategies_groups(root, metadata, variables, claimed_paths))
    groups.extend(_reclamation_groups(root, metadata, variables, claimed_paths))
    groups.extend(_other_story_groups(root, metadata, variables, claimed_paths))

    review_names = {
        group.id: group.name for group in groups if group.group_type in _GROUP_TYPES.values()
    }
    movements, sections = parse_score(root, review_names)
    review_groups = {group.id: group for group in groups}
    claimed_groups: set[str] = set()
    populated_sections = []
    for section in sections:
        group = review_groups.get(section.review_group_id or "")
        if group is None:
            populated_sections.append(section)
            continue
        if group.id in claimed_groups:
            raise ValueError(f"review group is claimed by multiple Movement Sections: {group.id}")
        claimed_groups.add(group.id)
        populated_sections.append(
            replace(
                section,
                name=group.name,
                stories=tuple(
                    replace(story, collection_id=section.collection_id) for story in group.stories
                ),
            )
        )

    archives = []
    for group in groups:
        if group.id in claimed_groups:
            continue
        if group.group_type == "main_story":
            raise ValueError(
                f"main-story review group is not owned by a Movement Section: {group.id}"
            )
        archive_kind, story_type = _archive_type(group.group_type)
        archives.append(
            ArchiveGroup(
                id=group.id,
                collection_id=f"archive_group:{group.id}",
                position=len(archives),
                name=group.name,
                archive_kind=archive_kind,
                story_type=story_type,
                stories=tuple(
                    replace(story, collection_id=f"archive_group:{group.id}")
                    for story in group.stories
                ),
            )
        )
    return movements, tuple(populated_sections), tuple(archives)


def _archive_type(group_type: str) -> tuple[str, str | None]:
    if group_type == "major_event":
        return "events", "side_story"
    if group_type == "minor_event":
        return "events", "vignette"
    if group_type in {
        "operator_record",
        "integrated_strategies",
        "reclamation_algorithm",
        "others",
    }:
        return group_type, None
    if group_type == "main_story":
        raise ValueError("main-story review groups cannot be archived")
    return "others", None


def _integrated_strategies_groups(
    root: Path,
    metadata: dict[str, tuple[str, str]],
    variables: Mapping[str, str],
    claimed_paths: set[str],
) -> tuple[_ParsedGroup, ...]:
    """Build one group per 集成战略 theme from its official ending catalog."""

    table = _read_json(root / _DATA_ROOT / "excel/roguelike_topic_table.json")
    topics = _mapping(_at(table, "topics"))
    details = _mapping(_at(table, "details"))
    review_meta = _read_json(root / _DATA_ROOT / "excel/story_review_meta_table.json")
    story_root = root / _DATA_ROOT / "story"

    # Monthly-squad scripts are chat logs with no indexed AVG artwork. Claim
    # their catalog paths so removing that category does not republish them as
    # remaining story files.
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
            source_directory = resolve_local_path(
                story_root,
                directory,
                context="story path",
            )
            if source_directory.is_dir():
                claimed_paths.update(
                    _story_key(path.relative_to(story_root).as_posix())
                    for path in source_directory.rglob("*.txt")
                )
        if stories:
            groups.append(
                _ParsedGroup(
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
) -> tuple[_ParsedGroup, ...]:
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
        directory = resolve_local_path(
            story_root,
            f"obt/sandboxperm/{topic_id}",
            context="story path",
        )
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
                _ParsedGroup(
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
) -> tuple[_ParsedGroup, ...]:
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
            _ParsedGroup(
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
        text = path.read_text(encoding="utf-8")
        directives = parse_directives(text)
    else:
        _INCOMPLETE_UPSTREAM_LOGGER.warning(
            "story text is missing; continuing without art references story_id=%s path=%s",
            id,
            f"gamedata/story/{story_path}.txt",
        )
        text = ""
        directives = ()
    return StoryRecord(
        id=id,
        collection_id=group_id,
        tag=tag,
        tag_text=tag_text,
        code=code,
        name=name,
        info=info,
        art_references=(*_pictures(directives, metadata), *_characters(directives, variables)),
        text=text,
        media_references=_media_references(directives, variables),
    )


def _story_key(value: str) -> str:
    path = safe_relative_path(value, context="story path")
    if path.suffix.lower() == ".txt":
        path = path.with_suffix("")
    return path.as_posix().lower()


def _story_path(root: Path, story_path: str) -> Path:
    return _game_data_path(root, f"story/{story_path}.txt")


def _path_id(prefix: str, story_path: str) -> str:
    return f"{prefix}:{story_path.replace('/', ':')}"


def parse_directives(raw: str) -> tuple[Directive, ...]:
    """Parse every well-formed bracketed command from one story text file.

    Story scripts are a small command language rather than a regular language:
    parameter values can contain commas, quotes, newlines, and nested
    parentheses, while newer scripts also use namespaced commands such as
    ``Battle.Pause``. A small scanner keeps the parser permissive for future
    commands without making the resource extractors guess at syntax.
    """

    if not isinstance(raw, str):
        raise TypeError("story text must be a string")
    directives: list[Directive] = []
    position = 0
    while True:
        start = raw.find("[", position)
        if start < 0:
            break
        end = _matching_bracket(raw, start)
        if end is None:
            position = start + 1
            continue
        directive = _parse_directive_body(raw[start + 1 : end])
        if directive is not None:
            _validate_directive_shape(directive)
            directives.append(directive)
        position = end + 1
    return tuple(directives)


def _matching_bracket(raw: str, start: int) -> int | None:
    """Find a command's closing bracket while respecting quoted parameters."""

    quote: str | None = None
    escaped = False
    parentheses = 0
    brackets = 0
    for position in range(start + 1, len(raw)):
        character = raw[position]
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
        elif character == "(":
            parentheses += 1
        elif character == ")" and parentheses:
            parentheses -= 1
        elif character == "[":
            brackets += 1
        elif character == "]":
            if brackets:
                brackets -= 1
            elif parentheses == 0:
                return position
    return None


def _matching_parenthesis(raw: str, start: int) -> int | None:
    """Find the closing parenthesis for a command parameter list."""

    quote: str | None = None
    escaped = False
    depth = 0
    for position in range(start, len(raw)):
        character = raw[position]
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return position
    return None


def _is_command_character(character: str) -> bool:
    return (character.isascii() and character.isalnum()) or character in {"_", ".", "-", ":"}


def _parse_directive_body(body: str) -> Directive | None:
    """Parse a command body without requiring a fixed command vocabulary."""

    body = body.strip()
    if not body:
        return None
    position = 0
    while position < len(body) and _is_command_character(body[position]):
        position += 1
    if position == 0:
        return None
    name = body[:position].lower()
    remainder = body[position:].lstrip()
    if name == "name" and remainder.startswith("="):
        # Speaker directives use ``[name="...", ...]`` rather than the
        # regular ``command(key=value)`` form.
        return Directive("", _parse_params("name" + remainder), source_name="name")
    if remainder.startswith("("):
        closing = _matching_parenthesis(remainder, 0)
        if closing is None:
            return None
        params = _parse_params(remainder[1:closing])
    else:
        params = _parse_params(remainder)
    if name == "name" and not body[position:].lstrip().startswith("("):
        return Directive("", params, source_name="name")
    return Directive(name, params)


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
        name = _directive_name(directive)
        if name == "image":
            add(directive.params.get("image", ""), "image")
        elif name == "background":
            add(directive.params.get("image", ""), "background")
        elif name in {"backgroundtween", "bgeffect", "largebgtween"}:
            add(directive.params.get("image", ""), "background")
            for identifier in directive.params.get("imagegroup", "").split("/"):
                add(identifier, "background")
        elif name in {"largebg", "gridbg", "verticalbg"}:
            for identifier in directive.params.get("imagegroup", "").split("/"):
                add(identifier, "background")
            add(directive.params.get("image", ""), "background")
        elif name in {"cgitem", "hidecgitem", "showitem"}:
            add(directive.params.get("image", ""), "item")
        elif name in {"imgeffect", "imagerotate", "imagetween"}:
            add(directive.params.get("image", ""), "image")
        elif name == "avgdisplay" and directive.params.get("style", "").lower() in {
            "animekv",
            "bg",
        }:
            # ``animekv`` is a Unity animated bundle, while ``bg`` is a
            # regular background. Both use a stable logical artwork name.
            add(directive.params.get("name", ""), "background")
    return tuple(pictures)


def _media_references(
    directives: tuple[Directive, ...],
    variables: Mapping[str, str] | None = None,
) -> tuple[StoryMediaReference, ...]:
    """Project sound, music, and video directives into stable media IDs."""

    references: list[StoryMediaReference] = []
    variables = variables or {}

    def add(identifier: str, kind: StoryMediaKind) -> None:
        identifier = _normalize_media_id(identifier, kind, variables)
        if not identifier:
            return
        reference = StoryMediaReference(media_id=identifier, kind=kind)
        if reference not in references:
            references.append(reference)

    for directive in directives:
        name = _directive_name(directive)
        if name in {"playsound", "voicewithin"}:
            for key in ("key", "voice", "sound", "res", "name"):
                if directive.params.get(key):
                    add(directive.params[key], "sound")
                    break
        elif name == "playmusic":
            for key in ("key", "intro"):
                add(directive.params.get(key, ""), "music")
        elif name == "video":
            add(directive.params.get("res", ""), "video")
    return tuple(references)


def _normalize_media_id(
    identifier: str,
    kind: StoryMediaKind,
    variables: Mapping[str, str],
) -> str:
    value = identifier.strip().strip('"').strip("'").lower()
    if kind in {"sound", "music"}:
        value = value.removeprefix("$")
        resolved = variables.get(value)
        if resolved:
            value = PurePosixPath(resolved.replace("\\", "/")).name
            value = PurePosixPath(value).stem.lower()
        return value
    if kind == "video":
        try:
            path = safe_relative_path(value, context="story video reference")
        except ValueError:
            return ""
        if path.suffix.lower() != ".mp4":
            return ""
        return path.as_posix()
    return ""


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
        elif _directive_name(directive) == "character":
            take("1", _resolve_character_id(directive.params.get("name", ""), variables))
            take("2", _resolve_character_id(directive.params.get("name2", ""), variables))
            spotlight = focus(directive.params.get("focus", ""))
        elif _directive_name(directive) == "charslot":
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
        elif _directive_name(directive) == "dialog":
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
    """Parse comma-separated key/value parameters without losing quoted data."""

    params: dict[str, str] = {}
    position = 0
    while position < len(raw):
        while position < len(raw):
            if raw[position] == "\\" and position + 1 < len(raw):
                if raw[position + 1] == "\n":
                    position += 2
                    continue
                if raw[position + 1] == "\r":
                    position += 2
                    if position < len(raw) and raw[position] == "\n":
                        position += 1
                    continue
            if raw[position] in " \t\r\n,":
                position += 1
                continue
            break
        if position >= len(raw):
            break
        key_start = position
        while position < len(raw) and raw[position] not in "=,":
            position += 1
        key = raw[key_start:position].strip().lower()
        if position >= len(raw) or raw[position] != "=":
            while position < len(raw) and raw[position] != ",":
                position += 1
            continue
        position += 1
        while position < len(raw) and raw[position].isspace():
            position += 1
        if position < len(raw) and raw[position] in {"'", '"'}:
            value, position = _read_quoted_value(raw, position)
        else:
            value_start = position
            depths = {"(": 0, "[": 0, "{": 0}
            closing = {")": "(", "]": "[", "}": "{"}
            while position < len(raw):
                character = raw[position]
                if character in depths:
                    depths[character] += 1
                elif character in closing and depths[closing[character]]:
                    depths[closing[character]] -= 1
                elif character == "," and not any(depths.values()):
                    break
                position += 1
            value = raw[value_start:position].strip()
        if key:
            params[key] = value
        while position < len(raw) and raw[position] != ",":
            position += 1
        if position < len(raw):
            position += 1
    return params


def _read_quoted_value(raw: str, start: int) -> tuple[str, int]:
    quote = raw[start]
    position = start + 1
    value: list[str] = []
    while position < len(raw):
        character = raw[position]
        if character == quote:
            return "".join(value), position + 1
        if character == "\\" and position + 1 < len(raw):
            value.append(raw[position + 1])
            position += 2
            continue
        value.append(character)
        position += 1
    return "".join(value), position


def _game_data_path(root: Path, relative: str) -> Path:
    return resolve_local_path(root / _DATA_ROOT, relative, context="game-data path")


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
