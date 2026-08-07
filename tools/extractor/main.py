import argparse
import functools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, Tuple

import PIL.Image
import UnityPy
from UnityPy.classes import Object, Texture2D, Sprite, TextAsset, MonoBehaviour, GameObject

from lz4ak import patch_unitypy

# Arknights reuses Unity's LZHAM flag for its LZ4AK bundle blocks.
patch_unitypy()

# flush every line to prevent blocking outputs
# noinspection PyShadowingBuiltins
print = functools.partial(print, flush=True)

# initialize PIL to preload supported formats
PIL.Image.preinit()
PIL.Image.init()


def normalize_container_path(container: Path) -> Path:
    """Map Arknights' short bundle paths to the tree used by the Go scanner."""
    if container.parts and container.parts[0].lower() == "dyn":
        return Path("assets", "torappu", "dynamicassets", *container.parts[1:])
    return container


def mono_behaviour_name(obj: MonoBehaviour, type_tree=None) -> str:
    """Get a useful class name even when UnityPy cannot resolve MonoScript.

    New Arknights character bundles refer to a shared MonoScript CAB that is
    not included in the individual bundle.  The serialized MonoBehaviour data
    is still usable; the sprite hub's type-tree shape is enough to recover the
    names the scanner expects.
    """
    try:
        script = obj.m_Script.read()
    except FileNotFoundError:
        script = None

    script_name = getattr(script, "m_Name", "") if script is not None else ""
    if script_name:
        return script_name

    if type_tree is None:
        type_tree = obj.object_reader.read_typetree()
    if "spriteGroups" in type_tree:
        return "AVGCharacterSpriteHubGroup"
    if "sprites" in type_tree:
        return "AVGCharacterSpriteHub"
    return f"MonoBehaviour_{obj.object_reader.path_id}"


def unpack_assets(src: Path, dst: Path, workers=None):
    try:
        if src.is_dir():
            print(f"searching files in {src}...")
            with ProcessPoolExecutor(max_workers=workers) as executor:
                for it in src.glob('**/*'):
                    if it.is_file():
                        print(f"found {it} in {src}...")
                        executor.submit(unpack_assets, it, dst, None)

        elif src.is_file():
            env = UnityPy.load(str(src))
            for container, obj_reader in env.container.items():
                container = normalize_container_path(Path(container))
                obj = obj_reader.read()

                dst_subdir = container / '..' / obj.m_Name
                path_id_path = (dst / container / '..' / f"{obj.m_Name}.json").resolve()
                tt_path_id_path = (dst / container / '..' / f"{obj.m_Name}.typetree.json").resolve()
                path_id_dict, tt_path_id_dict = export(obj, dst, dst_subdir)
                if len(path_id_dict) > 0:
                    with open(path_id_path, "w", encoding="utf8") as file:
                        json.dump(path_id_dict, file, ensure_ascii=False, indent=4)
                    with open(tt_path_id_path, "w", encoding="utf8") as file:
                        json.dump(tt_path_id_dict, file, ensure_ascii=False, indent=4)

        else:
            print(f"WARN: {src} is not dir neither file; skipping", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: {src} failed to unpack: {e}", file=sys.stderr)


def export(
        obj: Object, dst: Path, dst_subdir: Path,
        path_id_dict: Dict[int, str] = None,
        tt_path_id_dict: Dict[int, str] = None
) -> Tuple[Dict[int, str], Dict[int, str]]:
    path_id_dict = {} if path_id_dict is None else path_id_dict
    tt_path_id_dict = {} if tt_path_id_dict is None else tt_path_id_dict

    container = (
        normalize_container_path(Path(obj.object_reader.container))
        if obj.object_reader.container
        else None
    )

    obj_name = getattr(obj, 'm_Name', '')
    obj_type = obj.object_reader.type.name

    path_id = obj.object_reader.path_id

    match obj:
        case Texture2D() | Sprite():
            obj: Texture2D | Sprite

            obj_path = Path(os.path.normpath(container or dst_subdir / f"{obj_name}.png"))

            dest = (dst / (container or obj_path)).resolve()
            json_dest = (dst / (container or obj_path).with_suffix(f'.{obj_type}.json')).resolve()
            dest.parent.mkdir(parents=True, exist_ok=True)
            json_dest.parent.mkdir(parents=True, exist_ok=True)
            path_id_dict[path_id] = str(dest.name)
            tt_path_id_dict[path_id] = str(json_dest.name)

            if dest.exists() and obj_type in ["Sprite"]:
                # Sometimes there are some Sprite and Texture2D with the same name
                # Texture2D is preferred over Sprite, so we skip the Sprite
                # This is because Texture2D is usually the original image
                print(f"skipping {obj_path}({obj_type}), file already exists", file=sys.stderr)
            else:
                if dest.suffix in PIL.Image.EXTENSION and PIL.Image.EXTENSION[dest.suffix] in PIL.Image.SAVE:
                    obj.image.save(dest)
                    print(f"{obj_path}({obj_type})=>{dest}")
                else:
                    print(f"cannot export {obj_path}({obj_type}), format is not supported", file=sys.stderr)

            with open(json_dest, "w", encoding="utf8") as file:
                json.dump(obj.object_reader.read_typetree(), file,
                          ensure_ascii=False,
                          indent=4,
                          default=lambda o: '<non-serializable>')
            print(f"{obj_path}({obj_type})=>{json_dest}")

        case MonoBehaviour():
            obj: MonoBehaviour

            type_tree = obj.object_reader.read_typetree()
            obj_name = mono_behaviour_name(obj, type_tree)

            obj_path = Path(os.path.normpath(container or dst_subdir / f"{obj_name}.json"))

            dest = (dst / (container or obj_path)).resolve()
            dest.parent.mkdir(parents=True, exist_ok=True)
            path_id_dict[path_id] = str(dest.name)

            with open(dest, "w", encoding="utf8") as file:
                json.dump(type_tree, file,
                          ensure_ascii=False,
                          indent=4,
                          default=lambda o: '<non-serializable>')
            print(f"{obj_path}({obj_type})=>{dest}")

        case GameObject():
            obj: GameObject

            obj_readers = obj.assets_file.objects.values()
            dst_subdir = dst_subdir / '..' / obj_name
            for obj_reader in obj_readers:
                if obj_reader is obj.object_reader:
                    continue
                export(obj_reader.read(), dst, dst_subdir, path_id_dict, tt_path_id_dict)

        case _:
            print(f"skipping {obj_name}({obj_type}), type {obj_type} not supported", file=sys.stderr)

    return path_id_dict, tt_path_id_dict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "src", nargs="+",
        help="Path to source file or directory."
    )
    parser.add_argument(
        "dst",
        help="Path to destination directory."
    )
    parser.add_argument(
        "-w", "--workers", nargs="?", default=None,
        help="Specify the concurrency workers count."
    )
    args = parser.parse_args()

    for src in args.src:
        unpack_assets(
            Path(src),
            Path(args.dst),
            workers=int(args.workers) if args.workers else None
        )


if __name__ == '__main__':
    main()
