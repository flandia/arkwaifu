import pytest

from arkwaifu_updateloop.config import Settings


def _set_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARKWAIFU_S3_BUCKET", "bucket")
    monkeypatch.setenv("ARKWAIFU_S3_ACCESS_KEY_ID", "access-key")
    monkeypatch.setenv("ARKWAIFU_S3_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.delenv("ARKWAIFU_DOWNLOAD_WORKERS", raising=False)
    monkeypatch.delenv("ARKWAIFU_EXTRACTION_WORKERS", raising=False)
    monkeypatch.delenv("ARKWAIFU_ART_VERSION_URL", raising=False)
    monkeypatch.delenv("ARKWAIFU_ART_ASSET_BASE_URL", raising=False)
    monkeypatch.delenv("ARKWAIFU_DATABASE_URL", raising=False)


def test_database_url_is_not_required(monkeypatch):
    _set_required_environment(monkeypatch)

    settings = Settings.from_environment()

    assert not hasattr(settings, "database_url")


def test_art_defaults_use_the_official_windows_asset_roots(monkeypatch):
    _set_required_environment(monkeypatch)

    settings = Settings.from_environment()

    assert settings.art_version_url == (
        "https://ak-conf.hypergryph.com/config/prod/official/Windows/version"
    )
    assert settings.art_asset_base_url == (
        "https://ak.hycdn.cn/assetbundle/official/Windows/assets"
    )


def test_worker_defaults_use_sixteen_downloaders_and_default_process_count(monkeypatch):
    _set_required_environment(monkeypatch)

    settings = Settings.from_environment()

    assert settings.download_workers == 16
    assert settings.extraction_workers is None


def test_worker_counts_accept_positive_integers(monkeypatch):
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("ARKWAIFU_DOWNLOAD_WORKERS", "32")
    monkeypatch.setenv("ARKWAIFU_EXTRACTION_WORKERS", "4")

    settings = Settings.from_environment()

    assert settings.download_workers == 32
    assert settings.extraction_workers == 4


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("ARKWAIFU_DOWNLOAD_WORKERS", "0"),
        ("ARKWAIFU_DOWNLOAD_WORKERS", "-1"),
        ("ARKWAIFU_DOWNLOAD_WORKERS", "many"),
        ("ARKWAIFU_EXTRACTION_WORKERS", "0"),
        ("ARKWAIFU_EXTRACTION_WORKERS", "-1"),
        ("ARKWAIFU_EXTRACTION_WORKERS", "many"),
    ],
)
def test_worker_counts_reject_non_positive_and_non_integer_values(monkeypatch, name, value):
    _set_required_environment(monkeypatch)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=rf"^{name} must be a positive integer"):
        Settings.from_environment()
