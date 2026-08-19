from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from arkwaifu_updateloop.domain import (
    ArtworkManifest,
    FilePngArtifact,
    LocaleManifest,
    PngArtifact,
)


def image_artifact(color=(1, 2, 3, 255)) -> PngArtifact:
    return PngArtifact.from_image(Image.new("RGBA", (2, 3), color))


def test_png_encoding_is_deterministic_and_metadata_free():
    first = image_artifact()
    second = image_artifact()

    assert first.content == second.content
    assert not hasattr(first, "sha256")
    assert (first.width, first.height) == (2, 3)
    with Image.open(BytesIO(first.content)) as decoded:
        assert decoded.info == {}
        assert decoded.mode == "RGBA"


def test_png_artifact_validates_new_bytes_exactly_once(monkeypatch: pytest.MonkeyPatch):
    content = image_artifact().content
    real_open = Image.open
    opens = 0

    def counting_open(*args, **kwargs):
        nonlocal opens
        opens += 1
        return real_open(*args, **kwargs)

    monkeypatch.setattr("arkwaifu_updateloop.domain.Image.open", counting_open)

    artifact = PngArtifact.from_bytes(content)

    assert opens == 1
    assert artifact.content == content
    assert (artifact.width, artifact.height) == (2, 3)


def test_png_artifact_trusts_the_dimensions_of_an_encoded_image(
    monkeypatch: pytest.MonkeyPatch,
):
    def unexpected_open(*_args, **_kwargs):
        raise AssertionError("generated PNG was decoded again")

    monkeypatch.setattr("arkwaifu_updateloop.domain.Image.open", unexpected_open)

    artifact = PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255)))

    assert (artifact.width, artifact.height) == (2, 3)


def test_file_png_artifact_has_a_stable_path_and_loads_content_lazily(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    expected = image_artifact().content
    path = tmp_path / "image.png"
    path.write_bytes(expected)
    real_read_bytes = Path.read_bytes
    real_open = Image.open
    reads = 0
    opens = 0

    def counting_read_bytes(self: Path) -> bytes:
        nonlocal reads
        reads += 1
        return real_read_bytes(self)

    def counting_open(*args, **kwargs):
        nonlocal opens
        opens += 1
        return real_open(*args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", counting_read_bytes)
    monkeypatch.setattr("arkwaifu_updateloop.domain.Image.open", counting_open)

    artifact = FilePngArtifact.from_path(path)

    assert reads == 0
    assert opens == 1
    assert artifact.path == path.resolve()
    assert artifact.path.is_file()
    assert (artifact.width, artifact.height) == (2, 3)
    assert artifact.byte_size == len(expected)
    assert artifact.content == expected
    assert artifact.content == expected
    assert reads == 2
    assert opens == 1


def test_manifests_leave_validation_to_storage_constraints():
    assert not hasattr(ArtworkManifest, "validate")
    assert not hasattr(LocaleManifest, "validate")
