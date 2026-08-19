from __future__ import annotations

import struct
from dataclasses import replace
from pathlib import Path

import av
import pytest

from arkwaifu_updateloop.artwork import read_artwork_manifest, write_artwork_manifest
from arkwaifu_updateloop.artwork.video import (
    demux_usm_to_ivf,
    remux_ivf_to_webm,
    validate_ivf,
)
from arkwaifu_updateloop.domain import ArtworkManifest, ScoreVideoRecord


def _tiny_ivf(path: Path) -> bytes:
    with av.open(str(path), mode="w", format="ivf") as container:
        stream = container.add_stream("libvpx-vp9", rate=1)
        stream.width = 4
        stream.height = 4
        stream.pix_fmt = "yuv420p"
        frame = av.VideoFrame(4, 4, "yuv420p")
        for index, plane in enumerate(frame.planes):
            plane.update(bytes([16 if index == 0 else 128]) * plane.buffer_size)
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path.read_bytes()


def _tiny_adx(path: Path) -> bytes:
    with av.open(str(path), mode="w", format="adx") as container:
        stream = container.add_stream("adpcm_adx", rate=48_000)
        stream.layout = "stereo"
        frame = av.AudioFrame(format="s16", layout="stereo", samples=4_800)
        frame.sample_rate = 48_000
        for plane in frame.planes:
            plane.update(bytes(plane.buffer_size))
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path.read_bytes()


def _media_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    header = bytearray(24)
    header[1] = 24
    header[4] = 0
    header[7] = 0
    size = len(header) + len(payload)
    return chunk_type + struct.pack(">I", size) + header + payload


def _usm(ivf: bytes) -> bytes:
    crid = b"CRID" + struct.pack(">I", 1) + b"\0"
    return crid + _media_chunk(b"@SFV", ivf)


def test_score_usm_demux_and_lossless_webm_remux_are_deterministic(tmp_path: Path):
    ivf = _tiny_ivf(tmp_path / "source.ivf")
    usm = tmp_path / "score.usm"
    usm.write_bytes(_usm(ivf))

    metadata = demux_usm_to_ivf(usm, tmp_path / "demuxed.ivf")
    first = remux_ivf_to_webm(tmp_path / "demuxed.ivf", tmp_path / "first.webm", metadata)
    second = remux_ivf_to_webm(tmp_path / "demuxed.ivf", tmp_path / "second.webm", metadata)

    assert (metadata.width, metadata.height, metadata.frame_count) == (4, 4, 1)
    assert tmp_path.joinpath("demuxed.ivf").read_bytes() == ivf
    assert first.content == second.content
    assert first.byte_size > 0


def test_usm_preserves_embedded_audio_stream(tmp_path: Path):
    ivf = _tiny_ivf(tmp_path / "source.ivf")
    adx = _tiny_adx(tmp_path / "source.adx")
    source = tmp_path / "score.usm"
    video_destination = tmp_path / "output.ivf"
    audio_destination = tmp_path / "output.adx"
    source.write_bytes(_usm(ivf) + _media_chunk(b"@SFA", adx))

    metadata = demux_usm_to_ivf(source, video_destination, audio_destination)
    artifact = remux_ivf_to_webm(
        video_destination,
        tmp_path / "output.webm",
        metadata,
        audio_destination,
    )

    assert video_destination.read_bytes() == ivf
    assert audio_destination.read_bytes() == adx
    assert metadata.frame_count == 1
    with av.open(str(artifact.path), format="webm") as container:
        assert container.streams.audio[0].codec_context.name == "opus"


def test_score_webm_validation_rejects_a_lost_packet(tmp_path: Path):
    source = tmp_path / "source.ivf"
    metadata = validate_ivf(_tiny_ivf(source))

    with pytest.raises(ValueError, match="expected 2, found 1"):
        remux_ivf_to_webm(
            source,
            tmp_path / "output.webm",
            replace(metadata, frame_count=2),
        )


def test_score_video_manifest_uses_one_canonical_file_backed_artifact(tmp_path: Path):
    rendered = tmp_path / "rendered"
    source = tmp_path / "source.ivf"
    metadata = validate_ivf(_tiny_ivf(source))
    artifact = remux_ivf_to_webm(
        source,
        rendered / "processed/00000000.webm",
        metadata,
    )

    write_artwork_manifest(
        ArtworkManifest(
            "v1",
            (),
            (),
            score_videos=(ScoreVideoRecord("bg_mainline_0", artifact),),
        ),
        rendered,
    )
    cached = read_artwork_manifest(rendered)

    assert cached.score_videos[0].video.path == artifact.path
    assert [path.name for path in (rendered / "processed").iterdir()] == ["00000000.webm"]


def test_ivf_validation_rejects_truncated_frames(tmp_path: Path):
    ivf = _tiny_ivf(tmp_path / "source.ivf")

    with pytest.raises(ValueError, match="invalid IVF frame size"):
        validate_ivf(ivf[:-1])
