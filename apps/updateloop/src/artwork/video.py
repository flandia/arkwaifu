"""Fail-closed extraction of the VP9-in-IVF Score videos carried by CRI USM."""

from __future__ import annotations

import heapq
import struct
from contextlib import ExitStack
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


def demux_usm_to_ivf(
    source: Path,
    destination: Path,
    audio_destination: Path | None = None,
) -> IvfMetadata:
    """Extract channel-zero ``@SFV`` video and optional ``@SFA`` ADX audio."""

    content = source.read_bytes()
    if len(content) < 8 or content[:4] != b"CRID":
        raise ValueError(f"Score video is not a CRID USM: {source}")
    output = bytearray()
    audio_output = bytearray()
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
            if chunk_type == b"@SFA":
                if audio_destination is not None and payload_type == 0:
                    if channel != 0:
                        raise ValueError(f"unsupported USM audio channel {channel}")
                    audio_output.extend(content[payload_start:payload_end])
                position = chunk_end
                continue
            if chunk_type in {b"@ALP", b"@SBT"}:
                position = chunk_end
                continue
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
    if audio_destination is not None:
        audio_destination.unlink(missing_ok=True)
        if audio_output:
            audio_destination.parent.mkdir(parents=True, exist_ok=True)
            audio_destination.write_bytes(audio_output)
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
    audio_source: Path | None = None,
) -> FileVideoArtifact:
    """Remux VP9 losslessly and encode optional ADX audio as browser-native Opus."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        input_container = stack.enter_context(av.open(str(source), mode="r", format="ivf"))
        if len(input_container.streams.video) != 1 or input_container.streams.audio:
            raise ValueError("IVF input does not contain exactly one video stream")
        input_stream = input_container.streams.video[0]
        if input_stream.codec_context.name != "vp9":
            raise ValueError(f"IVF codec is not VP9: {input_stream.codec_context.name}")

        audio_container = None
        audio_stream = None
        audio_sample_count = None
        if audio_source is not None:
            with audio_source.open("rb") as input_file:
                audio_header = input_file.read(16)
            if len(audio_header) < 16:
                raise ValueError("USM ADX audio header is truncated")
            audio_sample_count = struct.unpack_from(">I", audio_header, 12)[0]
            if audio_sample_count <= 0:
                raise ValueError("USM ADX audio declares no samples")
            audio_container = stack.enter_context(
                av.open(str(audio_source), mode="r", format="adx")
            )
            if len(audio_container.streams.audio) != 1 or audio_container.streams.video:
                raise ValueError("ADX input does not contain exactly one audio stream")
            audio_stream = audio_container.streams.audio[0]
            if audio_stream.codec_context.name != "adpcm_adx":
                raise ValueError(f"USM audio codec is not ADX: {audio_stream.codec_context.name}")

        output_container = stack.enter_context(
            av.open(
                str(destination),
                mode="w",
                format="webm",
                options={"fflags": "+bitexact"},
            )
        )
        output_container.metadata.clear()
        output_stream = output_container.add_stream_from_template(input_stream)
        output_stream.metadata.clear()

        def video_packets():
            for packet in input_container.demux(input_stream):
                if packet.size > 0:
                    packet.stream = output_stream
                    yield packet

        packets = video_packets()
        if (
            audio_stream is not None
            and audio_container is not None
            and audio_sample_count is not None
        ):
            output_audio = output_container.add_stream(
                "libopus",
                rate=audio_stream.codec_context.sample_rate,
            )
            output_audio.layout = audio_stream.codec_context.layout
            output_audio.bit_rate = 96_000 * audio_stream.codec_context.channels
            output_audio.metadata.clear()

            def audio_packets():
                decoded_samples = 0
                for input_packet in audio_container.demux(audio_stream):
                    for frame in input_packet.decode():
                        decoded_samples += frame.samples
                        if decoded_samples > audio_sample_count:
                            raise ValueError("USM ADX audio exceeds its declared sample count")
                        yield from output_audio.encode(frame)
                    if decoded_samples == audio_sample_count:
                        break
                if decoded_samples != audio_sample_count:
                    raise ValueError(
                        "USM ADX audio sample count mismatch: "
                        f"expected {audio_sample_count}, decoded {decoded_samples}"
                    )
                yield from output_audio.encode()

            def packet_time(packet):
                timestamp = packet.dts if packet.dts is not None else packet.pts
                if timestamp is None:
                    raise ValueError("USM media packet has no timestamp")
                return timestamp * packet.time_base

            packets = heapq.merge(packets, audio_packets(), key=packet_time)

        for packet in packets:
            output_container.mux(packet)
    artifact = FileVideoArtifact.from_path(
        destination,
        width=metadata.width,
        height=metadata.height,
        frame_rate_numerator=metadata.frame_rate_numerator,
        frame_rate_denominator=metadata.frame_rate_denominator,
        frame_count=metadata.frame_count,
    )
    _validate_webm(artifact, expect_audio=audio_source is not None)
    return artifact


def _validate_webm(artifact: FileVideoArtifact, *, expect_audio: bool) -> None:
    with av.open(str(artifact.path), mode="r", format="webm") as container:
        if len(container.streams.video) != 1 or len(container.streams.audio) != int(expect_audio):
            raise ValueError("rendered WebM has unexpected video or audio streams")
        stream = container.streams.video[0]
        if stream.codec_context.name != "vp9":
            raise ValueError(f"rendered WebM codec is not VP9: {stream.codec_context.name}")
        if expect_audio and container.streams.audio[0].codec_context.name != "opus":
            raise ValueError("rendered WebM audio codec is not Opus")
        if (stream.codec_context.width, stream.codec_context.height) != (
            artifact.width,
            artifact.height,
        ):
            raise ValueError("rendered WebM dimensions changed during remux")
        packet_counts = {item.index: 0 for item in container.streams}
        for packet in container.demux():
            if packet.size > 0:
                packet_counts[packet.stream.index] += 1
        packet_count = packet_counts[stream.index]
        if packet_count != artifact.frame_count:
            raise ValueError(
                "rendered WebM packet count changed during remux: "
                f"expected {artifact.frame_count}, found {packet_count}"
            )
        if expect_audio and packet_counts[container.streams.audio[0].index] == 0:
            raise ValueError("rendered WebM audio stream is empty")
