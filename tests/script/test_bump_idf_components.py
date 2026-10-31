"""Unit tests for script/bump_idf_components.py."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any
import urllib.error

import pytest

sys.path.insert(0, str((Path(__file__).parent / ".." / ".." / "script").resolve()))

import bump_idf_components as bump_mod  # noqa: E402

MANIFEST = """\
dependencies:
  bblanchon/arduinojson:
    version: "7.4.3"
  espressif/mdns:
    version: 1.14.0
  espressif/esp-tflite-micro:
    version: 1.3.3~1
  espressif/lan87xx:
    version: "1.0.0"
    rules:
      - if: "idf_version >=6.0.0 && target in [esp32, esp32p4]"
  # Keep in sync with esphome/components/ethernet/__init__.py
  espressif/ch390:
    version: "0.3.0"
  espressif/ksz80xx:
    version: "1.0.0"
  esphome/noise-c:
    version: 0.1.31
  esphome/shorthand:
    version: ==2.1.0
  espressif/ranged:
    version: ^1.2.0
  fastled/FastLED:
    git: https://github.com/FastLED/FastLED.git
    version: d44c800a9e876a8394caefc2ce4915dd96dac77b
  esphome/local:
    version: "*"
    override_path: ../local
"""

MDNS_PY = """\
def to_code(config):
    if CORE.using_esp_idf:
        add_idf_component(name="espressif/mdns", ref="1.14.0")
"""

ZIGBEE_PY = """\
def to_code(config):
    esp32.add_idf_component(
        name="espressif/esp-zigbee-lib",
        ref="2.0.5",
    )
"""

NOISE_PY = """\
NOISE_C_VERSION = "0.1.31"
LIBSODIUM_VERSION = "1.10021.12"


def to_code(config):
    cg.add_library("esphome/noise-c", NOISE_C_VERSION)
    if CORE.using_esp_idf:
        add_idf_component(name="esphome/noise-c", ref=NOISE_C_VERSION)
        add_idf_component(name="esphome/libsodium", ref=LIBSODIUM_VERSION)
"""

BSEC_PY = """\
BSEC2_LIBRARY_VERSION = "1.10.2610"


def to_code(config):
    esp32.add_idf_component(
        name="boschsensortec/Bosch-BSEC2-Library",
        repo="https://github.com/esphome-libs/Bosch-BSEC2-Library",
        ref=BSEC2_LIBRARY_VERSION,
    )
"""

JSON_PY = """\
def to_code(config):
    if CORE.using_esp_idf:
        add_idf_component(name="bblanchon/arduinojson", ref="7.4.3")
    else:
        cg.add_library("bblanchon/ArduinoJson", "7.4.3")
"""

ETHERNET_PY = """\
_IDF6_ETHERNET_COMPONENTS = {
    "LAN8720": IDFRegistryComponent("espressif/lan87xx", "1.0.0"),
    "KSZ8081": IDFRegistryComponent("espressif/ksz80xx", "1.0.0"),
    "KSZ8081RNA": IDFRegistryComponent("espressif/ksz80xx", "1.0.0"),
    "CH390": IDFRegistryComponent("espressif/ch390", "0.3.0"),
}
"""

PLATFORMIO_INI = """\
[common:arduino]
lib_deps =
    esphome/noise-c@0.1.31                ; noise (api, ota)
    bblanchon/ArduinoJson@7.4.3           ; json
    lvgl/lvgl@9.6.0                       ; lvgl
    ESP32Async/AsyncTCP@3.4.5             ; async_tcp

[common:idf]
lib_deps =
    esphome/noise-c@0.1.31  ; used by noise (api, ota)
"""


def registry(
    versions: dict[str, list[dict[str, Any]]],
    platformio: dict[str, list[str]] | None = None,
) -> bump_mod.FetchJson:
    """A fake Espressif registry serving ``versions`` per component name,
    and a fake PlatformIO registry serving ``platformio`` per library."""

    def fetch(url: str) -> Any:
        if url.startswith(bump_mod.PLATFORMIO_API):
            owner, _, library = url.removeprefix(bump_mod.PLATFORMIO_API).split("/")
            names = (platformio or {}).get(f"{owner}/{library}")
            if names is None:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            return {
                "version": {"name": names[0]},
                "versions": [{"name": name} for name in names],
            }
        name = url.removeprefix(bump_mod.REGISTRY_API)
        return {"versions": versions[name]}

    return fetch


def release(version: str, **extra: Any) -> dict[str, Any]:
    return {"version": version, "yanked_at": None, **extra}


@pytest.mark.parametrize(
    ("older", "newer"),
    [
        ("1.14.0", "1.14.1"),
        ("1.9.9", "1.10.0"),
        ("1.3.3", "1.3.3~1"),
        ("1.3.3~1", "1.3.3~2"),
        ("1.0.0-rc1", "1.0.0"),
        ("1.0.0-beta.1", "1.0.0-rc.1"),
        ("1.10021.12", "1.10021.13"),
    ],
)
def test_version_ordering(older: str, newer: str) -> None:
    assert bump_mod.Version.parse(older) < bump_mod.Version.parse(newer)
    assert not bump_mod.Version.parse(newer) < bump_mod.Version.parse(older)


@pytest.mark.parametrize("text", ["1.2", "v1.2.3", "1.2.3.4", "latest", "*"])
def test_version_parse_rejects_non_releases(text: str) -> None:
    assert bump_mod.Version.parse(text) is None


def test_version_parse_ignores_build_metadata() -> None:
    assert bump_mod.Version.parse("1.2.3+abc") == bump_mod.Version(1, 2, 3)
    assert bump_mod.Version.parse("1.2.3-rc1").prerelease == "rc1"


def test_manifest_pins_keeps_exact_registry_pins_only() -> None:
    assert bump_mod.manifest_pins(MANIFEST) == {
        "bblanchon/arduinojson": "7.4.3",
        "espressif/mdns": "1.14.0",
        "espressif/esp-tflite-micro": "1.3.3~1",
        "espressif/lan87xx": "1.0.0",
        "espressif/ch390": "0.3.0",
        "espressif/ksz80xx": "1.0.0",
        "esphome/noise-c": "0.1.31",
        "esphome/shorthand": "2.1.0",
    }


def test_manifest_pins_rejects_malformed_manifest() -> None:
    with pytest.raises(bump_mod.BumpError, match="malformed manifest"):
        bump_mod.manifest_pins("just a string\n")


def test_latest_release_skips_yanked_and_prereleases() -> None:
    fetch = registry(
        {
            "espressif/mdns": [
                release("2.0.0-rc1"),
                {"version": "1.15.0", "yanked_at": "2026-10-01T00:00:00+00:00"},
                release("1.14.1", docs={"changelog": "https://example/changelog.md"}),
                release("1.14.0"),
                release("not-a-version"),
            ]
        }
    )
    assert bump_mod.latest_release("espressif/mdns", fetch) == (
        "1.14.1",
        "https://example/changelog.md",
    )


def test_latest_release_without_any_release() -> None:
    fetch = registry({"espressif/mdns": [release("2.0.0-rc1")]})
    with pytest.raises(bump_mod.BumpError, match="no release versions"):
        bump_mod.latest_release("espressif/mdns", fetch)


CURRENT_RELEASES = {
    name: [release(current)]
    for name, current in bump_mod.manifest_pins(MANIFEST).items()
}


def test_find_outdated(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fetch = registry(
        {
            **CURRENT_RELEASES,
            "espressif/mdns": [release("1.14.1"), release("1.14.0")],
            "espressif/esp-tflite-micro": [release("1.3.3~2"), release("1.3.3~1")],
            "esphome/noise-c": [release("0.1.32")],
        }
    )
    monkeypatch.setattr(bump_mod, "HOLD", {"esphome/noise-c": "needs api changes"})

    outdated = bump_mod.find_outdated(repo, fetch=fetch)

    assert [(o.name, o.current, o.latest) for o in outdated] == [
        ("espressif/mdns", "1.14.0", "1.14.1"),
        ("espressif/esp-tflite-micro", "1.3.3~1", "1.3.3~2"),
    ]
    assert outdated[0].url == (
        "https://components.espressif.com/components/espressif/mdns/versions/1.14.1"
    )


def test_find_outdated_filters_to_requested_names(repo: Path) -> None:
    fetch = registry(
        {
            "espressif/mdns": [release("1.14.1")],
            "esphome/noise-c": [release("0.1.32")],
        }
    )
    outdated = bump_mod.find_outdated(repo, {"espressif/mdns"}, fetch=fetch)
    assert [o.name for o in outdated] == ["espressif/mdns"]


def test_find_outdated_skips_pins_it_cannot_rewrite(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "esphome/components/mdns/__init__.py").write_text(
        'MDNS = "espressif/mdns"\nadd_idf_component(name=MDNS, ref="1.14.0")\n'
    )
    fetch = registry(
        {
            **CURRENT_RELEASES,
            "espressif/mdns": [release("1.14.1")],
            # A registry revision cannot go into the constant shared with
            # add_library.
            "esphome/noise-c": [release("0.1.31~1")],
        },
        {"esphome/noise-c": ["0.1.31"]},
    )

    assert bump_mod.find_outdated(repo, fetch=fetch) == []

    err = capsys.readouterr().err
    assert "skipping espressif/mdns: esphome/components/mdns/__init__.py" in err
    assert "skipping esphome/noise-c: NOISE_C_VERSION also pins" in err


def test_find_outdated_waits_for_platformio_registry(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    versions = {
        **CURRENT_RELEASES,
        "bblanchon/arduinojson": [release("7.4.4")],
        "esphome/noise-c": [release("0.1.32")],
    }

    # PlatformIO still serves the old releases: nothing to bump yet.
    fetch = registry(
        versions,
        {"bblanchon/ArduinoJson": ["7.4.3"], "esphome/noise-c": ["0.1.31"]},
    )
    assert bump_mod.find_outdated(repo, fetch=fetch) == []
    err = capsys.readouterr().err
    assert (
        "bblanchon/arduinojson: 7.4.3 -> 7.4.4 waits for bblanchon/ArduinoJson "
        "7.4.4 on the PlatformIO registry" in err
    )
    assert "esphome/noise-c: 0.1.31 -> 0.1.32 waits for esphome/noise-c" in err

    # A library the PlatformIO registry does not know at all waits as well.
    fetch = registry(versions, {})
    assert bump_mod.find_outdated(repo, fetch=fetch) == []

    # Both registries carry the release: bump.
    fetch = registry(
        versions,
        {"bblanchon/ArduinoJson": ["7.4.4", "7.4.3"], "esphome/noise-c": ["0.1.32"]},
    )
    assert [o.latest for o in bump_mod.find_outdated(repo, fetch=fetch)] == [
        "7.4.4",
        "0.1.32",
    ]


def test_find_outdated_revision_only_bump_needs_no_platformio_release(
    repo: Path,
) -> None:
    # json pins the PlatformIO side with its own literal, so an IDF-only
    # revision is fine and the PlatformIO registry is not consulted.
    fetch = registry(
        {**CURRENT_RELEASES, "bblanchon/arduinojson": [release("7.4.3~1")]}
    )
    assert [o.latest for o in bump_mod.find_outdated(repo, fetch=fetch)] == ["7.4.3~1"]


def test_platformio_twin(repo: Path) -> None:
    assert bump_mod.platformio_twin(repo, "bblanchon/arduinojson") == (
        "bblanchon/ArduinoJson"
    )
    assert bump_mod.platformio_twin(repo, "esphome/noise-c") == "esphome/noise-c"
    assert bump_mod.platformio_twin(repo, "espressif/mdns") is None

    # Only pinned through add_library, not platformio.ini.
    (repo / "platformio.ini").unlink()
    assert bump_mod.platformio_twin(repo, "bblanchon/arduinojson") == (
        "bblanchon/ArduinoJson"
    )


def test_platformio_has_raises_on_server_errors() -> None:
    def fetch(url: str) -> Any:
        raise urllib.error.HTTPError(url, 503, "Unavailable", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        bump_mod.platformio_has("esphome/noise-c", "0.1.32", fetch)


def test_rewrite_manifest_preserves_quoting_and_layout() -> None:
    text = bump_mod.rewrite_manifest(MANIFEST, "espressif/mdns", "1.14.0", "1.14.1")
    assert "  espressif/mdns:\n    version: 1.14.1\n" in text

    text = bump_mod.rewrite_manifest(text, "espressif/lan87xx", "1.0.0", "1.1.0")
    assert '  espressif/lan87xx:\n    version: "1.1.0"\n    rules:\n' in text
    # Another component at the same version is left alone.
    assert '  espressif/ksz80xx:\n    version: "1.0.0"\n' in text
    assert "# Keep in sync with esphome/components/ethernet/__init__.py" in text

    text = bump_mod.rewrite_manifest(
        text, "espressif/esp-tflite-micro", "1.3.3~1", "1.3.3~2"
    )
    assert "    version: 1.3.3~2\n" in text


def test_rewrite_manifest_requires_exact_match() -> None:
    with pytest.raises(bump_mod.BumpError, match="found 0 manifest pins"):
        bump_mod.rewrite_manifest(MANIFEST, "espressif/mdns", "1.13.0", "1.14.1")
    with pytest.raises(bump_mod.BumpError, match="found 0 manifest pins"):
        bump_mod.rewrite_manifest(MANIFEST, "espressif/missing", "1.0.0", "1.0.1")


def test_rewrite_python_inline_call() -> None:
    text, count = bump_mod.rewrite_python(MDNS_PY, "espressif/mdns", "1.14.0", "1.14.1")
    assert count == 1
    assert 'add_idf_component(name="espressif/mdns", ref="1.14.1")' in text


def test_rewrite_python_multiline_call() -> None:
    text, count = bump_mod.rewrite_python(
        ZIGBEE_PY, "espressif/esp-zigbee-lib", "2.0.5", "2.0.6"
    )
    assert count == 1
    assert '        ref="2.0.6",\n' in text


def test_rewrite_python_constant_pin() -> None:
    text, count = bump_mod.rewrite_python(
        NOISE_PY, "esphome/noise-c", "0.1.31", "0.1.32"
    )
    assert count == 1
    assert 'NOISE_C_VERSION = "0.1.32"\n' in text
    assert 'LIBSODIUM_VERSION = "1.10021.12"\n' in text


def test_rewrite_python_constant_pin_with_repo() -> None:
    text, count = bump_mod.rewrite_python(
        BSEC_PY, "boschsensortec/Bosch-BSEC2-Library", "1.10.2610", "1.10.2700"
    )
    assert count == 1
    assert 'BSEC2_LIBRARY_VERSION = "1.10.2700"\n' in text


def test_rewrite_python_shared_constant_rejects_registry_revision() -> None:
    with pytest.raises(bump_mod.BumpError, match="needs a manual split"):
        bump_mod.rewrite_python(NOISE_PY, "esphome/noise-c", "0.1.31", "0.1.31~1")


def test_rewrite_python_add_library_twin() -> None:
    text, count = bump_mod.rewrite_python(
        JSON_PY, "bblanchon/arduinojson", "7.4.3", "7.4.4~1"
    )
    assert count == 2
    assert 'add_idf_component(name="bblanchon/arduinojson", ref="7.4.4~1")' in text
    assert 'cg.add_library("bblanchon/ArduinoJson", "7.4.4")' in text

    # A revision-only bump has nothing to change on the PlatformIO side.
    text, count = bump_mod.rewrite_python(
        JSON_PY, "bblanchon/arduinojson", "7.4.3", "7.4.3~1"
    )
    assert count == 1
    assert 'cg.add_library("bblanchon/ArduinoJson", "7.4.3")' in text


def test_rewrite_python_registry_component_table() -> None:
    text, count = bump_mod.rewrite_python(
        ETHERNET_PY, "espressif/ksz80xx", "1.0.0", "1.0.1"
    )
    assert count == 2
    assert text.count('IDFRegistryComponent("espressif/ksz80xx", "1.0.1")') == 2
    # lan87xx shares the old version string and must not change.
    assert 'IDFRegistryComponent("espressif/lan87xx", "1.0.0")' in text


def test_rewrite_python_unknown_layout() -> None:
    text = 'IDF_COMPONENTS = ["espressif/mdns"]\nVERSION = "1.14.0"\n'
    assert bump_mod.rewrite_python(text, "espressif/mdns", "1.14.0", "1.14.1") == (
        text,
        0,
    )


def test_rewrite_platformio_is_case_insensitive() -> None:
    text, count = bump_mod.rewrite_platformio(
        PLATFORMIO_INI, "bblanchon/arduinojson", "7.4.3", "7.4.4"
    )
    assert count == 1
    assert "    bblanchon/ArduinoJson@7.4.4           ; json\n" in text

    text, count = bump_mod.rewrite_platformio(
        PLATFORMIO_INI, "esphome/noise-c", "0.1.31", "0.1.32"
    )
    assert count == 2
    assert "esphome/noise-c@0.1.31" not in text


def test_rewrite_platformio_drops_registry_revision() -> None:
    # A ~revision is a registry re-upload of the same library release.
    text, count = bump_mod.rewrite_platformio(
        PLATFORMIO_INI, "lvgl/lvgl", "9.6.0", "9.6.0~1"
    )
    assert count == 0
    assert text == PLATFORMIO_INI

    text, count = bump_mod.rewrite_platformio(
        PLATFORMIO_INI, "lvgl/lvgl", "9.6.0~1", "9.7.0~2"
    )
    assert count == 1
    assert "    lvgl/lvgl@9.7.0                       ; lvgl\n" in text


def test_rewrite_platformio_leaves_other_versions_alone() -> None:
    # The PlatformIO registry carries a different release than the IDF one.
    text, count = bump_mod.rewrite_platformio(
        PLATFORMIO_INI, "esp32async/asynctcp", "3.4.91", "3.4.92"
    )
    assert count == 0
    assert text == PLATFORMIO_INI


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "esphome").mkdir()
    (tmp_path / "esphome" / "idf_component.yml").write_text(MANIFEST)
    components = tmp_path / "esphome" / "components"
    for name, text in {
        "mdns": MDNS_PY,
        "noise": NOISE_PY,
        "json": JSON_PY,
        "ethernet": ETHERNET_PY,
    }.items():
        (components / name).mkdir(parents=True)
        (components / name / "__init__.py").write_text(text)
    (tmp_path / "platformio.ini").write_text(PLATFORMIO_INI)
    return tmp_path


def test_bump_rewrites_every_copy_of_the_pin(repo: Path) -> None:
    changed = bump_mod.bump(repo, "esphome/noise-c", "0.1.32")

    assert changed == [
        Path("esphome/idf_component.yml"),
        Path("esphome/components/noise/__init__.py"),
        Path("platformio.ini"),
    ]
    assert (
        "  esphome/noise-c:\n    version: 0.1.32\n"
        in (repo / "esphome/idf_component.yml").read_text()
    )
    assert (
        'NOISE_C_VERSION = "0.1.32"'
        in (repo / "esphome/components/noise/__init__.py").read_text()
    )
    assert "esphome/noise-c@0.1.32" in (repo / "platformio.ini").read_text()


def test_bump_without_platformio_pin(repo: Path) -> None:
    changed = bump_mod.bump(repo, "espressif/ch390", "0.4.0")
    assert changed == [
        Path("esphome/idf_component.yml"),
        Path("esphome/components/ethernet/__init__.py"),
    ]
    assert (repo / "platformio.ini").read_text() == PLATFORMIO_INI


def test_bump_rejects_unknown_or_current_version(repo: Path) -> None:
    with pytest.raises(bump_mod.BumpError, match="not pinned"):
        bump_mod.bump(repo, "espressif/missing", "1.0.0")
    with pytest.raises(bump_mod.BumpError, match="already at"):
        bump_mod.bump(repo, "espressif/mdns", "1.14.0")


def test_bump_writes_nothing_on_error(repo: Path) -> None:
    before = {path: path.read_text() for path in repo.rglob("*") if path.is_file()}
    with pytest.raises(bump_mod.BumpError, match="needs a manual split"):
        bump_mod.bump(repo, "esphome/noise-c", "0.1.31~1")
    assert {path: path.read_text() for path in before} == before


def test_bump_fails_when_python_pin_is_not_recognised(repo: Path) -> None:
    (repo / "esphome/components/mdns/__init__.py").write_text(
        'MDNS = "espressif/mdns"\nadd_idf_component(name=MDNS, ref="1.14.0")\n'
    )
    with pytest.raises(bump_mod.BumpError, match="no pin at 1.14.0 was recognised"):
        bump_mod.bump(repo, "espressif/mdns", "1.14.1")


def test_main_list_prints_json(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    versions = {
        name: [release(current)]
        for name, current in bump_mod.manifest_pins(MANIFEST).items()
    }
    versions["espressif/mdns"].insert(
        0, release("1.14.1", docs={"changelog": "https://example/changelog.md"})
    )
    monkeypatch.setattr(bump_mod, "fetch_json", registry(versions))

    assert bump_mod.main(["--root", str(repo), "list"]) == 0

    captured = capsys.readouterr()
    assert captured.err == "espressif/mdns: 1.14.0 -> 1.14.1\n"
    assert captured.out == (
        '[{"name": "espressif/mdns", "current": "1.14.0", "latest": "1.14.1", '
        '"url": "https://components.espressif.com/components/espressif/mdns/versions/1.14.1", '
        '"changelog": "https://example/changelog.md"}]\n'
    )


def test_main_bump_reports_changed_files(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bump_mod.main(["--root", str(repo), "bump", "espressif/mdns", "1.14.1"]) == 0
    assert capsys.readouterr().out == (
        "updated esphome/idf_component.yml\n"
        "updated esphome/components/mdns/__init__.py\n"
    )


def test_main_bump_error_exit_code(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bump_mod.main(["--root", str(repo), "bump", "espressif/mdns", "1.14.0"]) == 1
    assert "error: espressif/mdns: already at 1.14.0" in capsys.readouterr().err
