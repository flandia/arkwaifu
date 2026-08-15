"""Fail-closed extraction of the VP9-in-IVF Score videos carried by CRI USM."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import av

from ..domain import FileVideoArtifact

_MEDIA_TYPES = {b"@SFV", b"@SFA", b"@ALP", b"@SBT"}


@dataclass(frozen=True, slots=True)
class IvfMetadata:
    """Describe the one accepted elementary VP9 stream."""

    width: int
    height: int
    frame_rate_numerator: int
    frame_rate_denominator: int
    frame_count: int


def demux_usm_to_ivf(source: Path, destination: Path) -> IvfMetadata:
    """Extract channel-zero ``@SFV`` payloads and reject every other media shape."""

    content = source.read_bytes()
    if len(content) < 8 or content[:4] != b"CRID":
        raise ValueError(f"Score video is not a CRID USM: {source}")
    output = bytearray()
    position = 0
    saw_video = False
    while position < len(content):
        if len(content) - position < 8:
            raise ValueError(f"truncated USM chunk header at offset {position}")
        chunk_type = content[position : position + 4]
        size = struct.unpack_from(">I", content, position + 4)[0]
        chunk_end = position + 8 + size
        if size == 0 or chunk_end > len(content):
            raise ValueError(f"invalid USM chunk size at offset {position}: {size}")
        if chunk_type in _MEDIA_TYPES:
            if size < 24:
                raise ValueError(f"truncated USM media header at offset {position}")
            payload_offset = content[position + 9]
            padding_size = struct.unpack_from(">H", content, position + 10)[0]
            channel = content[position + 12]
            payload_type = content[position + 15]
            payload_start = position + 8 + payload_offset
            payload_end = chunk_end - padding_size
            if payload_offset < 24 or payload_start > payload_end or payload_end > chunk_end:
                raise ValueError(f"invalid USM media payload at offset {position}")
            if chunk_type != b"@SFV":
                raise ValueError(
                    f"unsupported USM media stream {chunk_type.decode('ascii')} at offset {position}"
                )
            if channel != 0:
                raise ValueError(f"unsupported USM video channel {channel}")
            saw_video = True
            if payload_type == 0:
                output.extend(content[payload_start:payload_end])
        position = chunk_end
    if position != len(content) or not saw_video or not output:
        raise ValueError("USM contains no channel-zero video payload")

    metadata = validate_ivf(bytes(output))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    return metadata


def validate_ivf(content: bytes) -> IvfMetadata:
    """Validate the complete elementary stream and return its declared metadata."""

    if len(content) < 32 or content[:4] != b"DKIF":
        raise ValueError("USM video payload is not IVF")
    version, header_size = struct.unpack_from("<HH", content, 4)
    if version != 0 or header_size != 32 or content[8:12] != b"VP90":
        raise ValueError("USM video is not the supported VP9 IVF profile")
    width, height = struct.unpack_from("<HH", content, 12)
    numerator, denominator, declared_frames = struct.unpack_from("<III", content, 16)
    if min(width, height, numerator, denominator, declared_frames) <= 0:
        raise ValueError("IVF declares invalid stream metadata")
    position = header_size
    frames = 0
    while position < len(content):
        if len(content) - position < 12:
            raise ValueError(f"truncated IVF frame header at offset {position}")
        frame_size = struct.unpack_from("<I", content, position)[0]
        position += 12
        frame_end = position + frame_size
        if frame_size == 0 or frame_end > len(content):
            raise ValueError(f"invalid IVF frame size at offset {position - 12}: {frame_size}")
        frames += 1
        position = frame_end
    if frames != declared_frames:
        raise ValueError(f"IVF frame count mismatch: declared {declared_frames}, found {frames}")
    return IvfMetadata(width, height, numerator, denominator, frames)


def remux_ivf_to_webm(
    source: Path,
    destination: Path,
    metadata: IvfMetadata,
) -> FileVideoArtifact:
    """Losslessly remux one validated IVF stream into browser-native WebM."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(source), mode="r", format="ivf") as input_container:
        if len(input_container.streams.video) != 1 or input_container.streams.audio:
            raise ValueError("IVF input does not contain exactly one video stream")
        input_stream = input_container.streams.video[0]
        if input_stream.codec_context.name != "vp9":
            raise ValueError(f"IVF codec is not VP9: {input_stream.codec_context.name}")
        with av.open(
            str(destination),
            mode="w",
            format="webm",
            options={"fflags": "+bitexact"},
        ) as output_container:
            output_container.metadata.clear()
            output_stream = output_container.add_stream_from_template(input_stream)
            output_stream.metadata.clear()
            for packet in input_container.demux(input_stream):
                # PyAV emits one final, truly empty flushing packet. Packets
                # with bytes are retained even when DTS is absent.
                if packet.size == 0:
                    continue
                packet.stream = output_stream
                output_container.mux(packet)
    artifact = FileVideoArtifact.from_path(
        destination,
        width=metadata.width,
        height=metadata.height,
        frame_rate_numerator=metadata.frame_rate_numerator,
        frame_rate_denominator=metadata.frame_rate_denominator,
        frame_count=metadata.frame_count,
    )
    _validate_webm(artifact)
    return artifact


def _validate_webm(artifact: FileVideoArtifact) -> None:
    with av.open(str(artifact.path), mode="r", format="webm") as container:
        if len(container.streams.video) != 1 or container.streams.audio:
            raise ValueError("rendered WebM does not contain exactly one video stream")
        stream = container.streams.video[0]
        if stream.codec_context.name != "vp9":
            raise ValueError(f"rendered WebM codec is not VP9: {stream.codec_context.name}")
        if (stream.codec_context.width, stream.codec_context.height) != (
            artifact.width,
            artifact.height,
        ):
            raise ValueError("rendered WebM dimensions changed during remux")
        packet_count = sum(1 for packet in container.demux(stream) if packet.size > 0)
        if packet_count != artifact.frame_count:
            raise ValueError(
                "rendered WebM packet count changed during remux: "
                f"expected {artifact.frame_count}, found {packet_count}"
            )
