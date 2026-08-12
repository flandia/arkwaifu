from io import BytesIO

from PIL import Image

from arkwaifu_updateloop.domain import FilePngArtifact, PngArtifact
from arkwaifu_updateloop.thumbnail import make_thumbnail, thumbnail_object_key


def test_thumbnail_fits_without_upscaling_and_preserves_alpha():
    large = PngArtifact.from_image(Image.new("RGBA", (1024, 256), (20, 40, 60, 0)))
    small = PngArtifact.from_image(Image.new("RGBA", (64, 32), (20, 40, 60, 128)))

    fitted = make_thumbnail(large)
    unchanged = make_thumbnail(small)

    with Image.open(BytesIO(fitted)) as decoded:
        assert decoded.format == "WEBP"
        assert decoded.mode == "RGBA"
        assert decoded.size == (512, 128)
        assert decoded.getchannel("A").getextrema() == (0, 0)
    with Image.open(BytesIO(unchanged)) as decoded:
        assert decoded.size == (64, 32)


def test_file_backed_thumbnail_preserves_partial_alpha(tmp_path):
    path = tmp_path / "source.png"
    Image.new("RGBA", (32, 64), (20, 40, 60, 128)).save(path, format="PNG")

    content = make_thumbnail(FilePngArtifact.from_path(path))

    with Image.open(BytesIO(content)) as decoded:
        assert decoded.size == (32, 64)
        assert decoded.getchannel("A").getextrema() == (128, 128)


def test_thumbnail_key_uses_derived_variant_path_and_escaped_identity():
    assert (
        thumbnail_object_key(
            res_version="v1",
            category="character",
            identifier="char#1$2",
        )
        == "ART/v1/thumbnail/character/char%231%242.webp"
    )
