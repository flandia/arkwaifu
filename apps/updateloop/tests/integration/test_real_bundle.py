from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from arkwaifu_updateloop import MemoryObjectStore, Update, Updateloop
from arkwaifu_updateloop.art import build_art_manifest
from arkwaifu_updateloop.extraction import extract_assets

pytestmark = pytest.mark.skipif(
    os.environ.get("ARKWAIFU_INTEGRATION") != "1" or not os.environ.get("ARKWAIFU_REAL_BUNDLE"),
    reason="set ARKWAIFU_INTEGRATION=1 and ARKWAIFU_REAL_BUNDLE for the bundle smoke test",
)


async def test_real_bundle_extracts_processes_and_publishes(tmp_path: Path):
    bundle = Path(os.environ["ARKWAIFU_REAL_BUNDLE"])
    extracted = tmp_path / "extracted"
    extract_assets([bundle], extracted, workers=1)
    version = f"bundle-fixture-{uuid4().hex}"
    manifest = build_art_manifest(extracted, version)

    assert "avg_4193_lemuen_1#1$1" in {art.id for art in manifest.arts}
    assert len(manifest.arts) == 26
    assert len(manifest.source_arts) == 26
    assert {source.role for source in manifest.source_arts} == {"whole_body"}

    remote = MemoryObjectStore()

    async def build(_active, _force):
        return manifest

    result = await Updateloop(remote).run([Update("art", version, build)])
    assert result[0].status == "updated"
    assert remote.database is not None
    assert len(remote.objects) == (2 * len(manifest.arts)) + len(manifest.source_arts)
    assert all(key.startswith(f"ART/{version}/") for key in remote.objects)
