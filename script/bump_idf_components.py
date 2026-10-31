#!/usr/bin/env python3
"""Bump managed ESP-IDF component pins to their latest registry release.

Managed components from the Espressif Component Registry are pinned in
``esphome/idf_component.yml`` and again in the Python module that calls
``add_idf_component`` for them. A few libraries are published to the
PlatformIO registry as well and pinned a third time through
``cg.add_library`` and ``platformio.ini``. Dependabot cannot see either
registry, so this script treats the manifest as the source of truth, asks
the Espressif registry for newer releases and rewrites every copy of the
pin; a library with a PlatformIO twin is only bumped once that registry
carries the release too, so the pull request can pass the Arduino builds.

    bump_idf_components.py list             # JSON list of outdated pins
    bump_idf_components.py bump NS/NAME VER  # rewrite the pins for one

Pins that must stay behind (an upstream regression, a release that needs
code changes first) go in ``HOLD`` below with the reason; the scheduled
workflow then stops opening pull requests for them.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from functools import total_ordering
import json
from pathlib import Path
import re
import sys
import time
from typing import Any
import urllib.error
import urllib.request

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path("esphome/idf_component.yml")
PLATFORMIO_INI = Path("platformio.ini")
COMPONENTS_DIR = Path("esphome/components")

REGISTRY_URL = "https://components.espressif.com"
REGISTRY_API = f"{REGISTRY_URL}/api/components/"
PLATFORMIO_API = "https://api.registry.platformio.org/v3/packages/"

# Components deliberately held at their current pin, with the reason.
HOLD: dict[str, str] = {}

FetchJson = Callable[[str], Any]


class BumpError(Exception):
    """A pin could not be located, parsed or rewritten."""


@total_ordering
@dataclass(frozen=True)
class Version:
    """A registry version: ``MAJOR.MINOR.PATCH[~REVISION][-PRERELEASE]``."""

    major: int
    minor: int
    patch: int
    revision: int = 0
    prerelease: str | None = None

    _PATTERN = re.compile(
        r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
        r"(?:~(?P<revision>\d+))?"
        r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
        r"(?:\+[0-9A-Za-z.-]+)?$"
    )

    @classmethod
    def parse(cls, text: str) -> Version | None:
        """Parse ``text``, or return None when it is not a release version."""
        match = cls._PATTERN.match(text)
        if match is None:
            return None
        return cls(
            int(match["major"]),
            int(match["minor"]),
            int(match["patch"]),
            int(match["revision"] or 0),
            match["prerelease"],
        )

    def _key(self) -> tuple[int, int, int, int, int, str]:
        # A release sorts after every prerelease of the same version.
        return (
            self.major,
            self.minor,
            self.patch,
            self.revision,
            self.prerelease is None,
            self.prerelease or "",
        )

    def __lt__(self, other: Version) -> bool:
        return self._key() < other._key()


@dataclass(frozen=True)
class Outdated:
    """A manifest pin with a newer release on the registry."""

    name: str
    current: str
    latest: str
    changelog: str | None

    @property
    def url(self) -> str:
        return f"{REGISTRY_URL}/components/{self.name}/versions/{self.latest}"


def manifest_pins(text: str) -> dict[str, str]:
    """Exactly-pinned registry dependencies of an ``idf_component.yml``."""
    doc = yaml.safe_load(text)
    try:
        dependencies = doc["dependencies"]
    except (KeyError, TypeError):
        raise BumpError("malformed manifest: no dependencies mapping") from None
    pins: dict[str, str] = {}
    for name, entry in dependencies.items():
        if not isinstance(entry, dict) or not {
            "git",
            "path",
            "override_path",
        }.isdisjoint(entry):
            continue
        version = entry.get("version")
        if not isinstance(version, str):
            continue
        # Exact versions start with a digit; range operators are prefixes.
        version = version.removeprefix("==")
        if version[:1].isdigit() and "*" not in version:
            pins[name] = version
    return pins


def fetch_json(url: str, attempts: int = 3) -> Any:
    """GET ``url`` as JSON, retrying transient registry failures."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "esphome-bump-idf-components"}
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as err:
            if err.code < 500 or attempt == attempts:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts:
                raise
        time.sleep(2**attempt)
    raise AssertionError("unreachable")


def latest_release(name: str, fetch: FetchJson = fetch_json) -> tuple[str, str | None]:
    """The newest non-yanked release of ``name`` and its changelog URL."""
    doc = fetch(f"{REGISTRY_API}{name}")
    best: tuple[Version, str, str | None] | None = None
    for entry in doc.get("versions", []):
        if entry.get("yanked_at") is not None:
            continue
        text = entry.get("version", "")
        version = Version.parse(text)
        if version is None or version.prerelease is not None:
            continue
        if best is None or best[0] < version:
            docs = entry.get("docs") or {}
            best = (version, text, docs.get("changelog"))
    if best is None:
        raise BumpError(f"{name}: no release versions on the registry")
    return best[1], best[2]


def platformio_twin(root: Path, name: str) -> str | None:
    """The PlatformIO spelling of ``name`` when the library is pinned there too.

    Looks for ``owner/Name@version`` in platformio.ini and
    ``add_library("owner/Name", ...)`` in the components; the PlatformIO
    registry keeps the owner's capitalisation.
    """
    escaped = re.escape(name)
    platformio_path = root / PLATFORMIO_INI
    if platformio_path.is_file() and (
        match := re.search(
            rf"(?im)^\s*({escaped})@", platformio_path.read_text(encoding="utf-8")
        )
    ):
        return match[1]
    for path in sorted((root / COMPONENTS_DIR).rglob("*.py")):
        if match := re.search(
            rf'add_library\(\s*"((?i:{escaped}))"', path.read_text(encoding="utf-8")
        ):
            return match[1]
    return None


def platformio_has(twin: str, version: str, fetch: FetchJson = fetch_json) -> bool:
    """Whether the PlatformIO registry carries ``version`` of library ``twin``."""
    owner, _, library = twin.partition("/")
    try:
        doc = fetch(f"{PLATFORMIO_API}{owner}/library/{library}")
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return False
        raise
    names = {entry.get("name") for entry in doc.get("versions") or []}
    if isinstance(latest := doc.get("version"), dict):
        names.add(latest.get("name"))
    return version in names


def find_outdated(
    root: Path,
    only: set[str] | None = None,
    fetch: FetchJson = fetch_json,
) -> list[Outdated]:
    """Manifest pins with a newer release that the script can apply.

    Skips ``HOLD`` entries, pins whose layout ``plan_bump`` cannot rewrite
    and libraries whose PlatformIO twin does not carry the release yet, so
    every entry returned becomes a pull request that can pass CI.
    """
    manifest_text = (root / MANIFEST).read_text(encoding="utf-8")
    outdated: list[Outdated] = []
    for name, current in manifest_pins(manifest_text).items():
        if only is not None and name not in only:
            continue
        if name in HOLD:
            print(f"{name}: held at {current} ({HOLD[name]})", file=sys.stderr)
            continue
        pinned = Version.parse(current)
        if pinned is None:
            print(f"{name}: cannot parse pinned version {current}", file=sys.stderr)
            continue
        latest, changelog = latest_release(name, fetch)
        if Version.parse(latest) <= pinned:
            continue
        try:
            plan_bump(root, name, latest)
        except BumpError as err:
            print(f"skipping {err}", file=sys.stderr)
            continue
        if (twin := platformio_twin(root, name)) is not None:
            base = _base_version(latest)
            if base != _base_version(current) and not platformio_has(twin, base, fetch):
                print(
                    f"{name}: {current} -> {latest} waits for {twin} {base} "
                    "on the PlatformIO registry",
                    file=sys.stderr,
                )
                continue
        outdated.append(Outdated(name, current, latest, changelog))
    return outdated


def rewrite_manifest(text: str, name: str, old: str, new: str) -> str:
    """Rewrite the ``version`` of ``name`` in a manifest, keeping its quoting."""
    pattern = re.compile(
        rf"(?m)^(  {re.escape(name)}:\n(?:    .*\n)*?    version:\s*([\"']?)){re.escape(old)}(\2[ \t]*(?:#.*)?)$"
    )
    rewritten, count = pattern.subn(rf"\g<1>{new}\g<3>", text, count=2)
    if count != 1:
        raise BumpError(f"{name}: found {count} manifest pins at {old}, expected 1")
    return rewritten


def rewrite_python(text: str, name: str, old: str, new: str) -> tuple[str, int]:
    """Rewrite every pin of ``name`` at ``old`` in a Python module.

    Handles ``add_idf_component(name=..., ref="1.2.3")``, the same call with
    ``ref=SOME_CONSTANT`` (the constant's assignment is rewritten),
    ethernet's ``IDFRegistryComponent("ns/name", "1.2.3")`` table and the
    PlatformIO twin ``cg.add_library("ns/Name", "1.2.3")`` of a library
    published to both registries.
    """
    quoted = re.escape(f'"{name}"')
    escaped_old = re.escape(old)
    call = rf"name\s*=\s*{quoted}\s*,(?:\s*repo\s*=\s*[^,]+,)?\s*ref\s*=\s*"
    total = 0

    text, count = re.subn(rf'({call}"){escaped_old}(")', rf"\g<1>{new}\g<2>", text)
    total += count

    for constant in set(re.findall(rf"{call}([A-Za-z_][A-Za-z0-9_]*)\b", text)):
        text, count = re.subn(
            rf'(?m)^({re.escape(constant)}\s*=\s*"){escaped_old}(")',
            rf"\g<1>{new}\g<2>",
            text,
        )
        total += count
        # The PlatformIO registry has no ~revision re-uploads, so a constant
        # shared with add_library cannot carry one.
        if "~" in new and re.search(rf"add_library\([^)]*\b{constant}\b", text):
            raise BumpError(
                f"{name}: {constant} also pins the PlatformIO library; "
                f"registry revision {new} needs a manual split"
            )

    text, count = re.subn(
        rf'({quoted},\s*"){escaped_old}(")', rf"\g<1>{new}\g<2>", text
    )
    total += count

    old_base, new_base = _base_version(old), _base_version(new)
    if old_base != new_base:
        text, count = re.subn(
            rf'(add_library\(\s*"(?i:{re.escape(name)})"\s*,\s*"){re.escape(old_base)}(")',
            rf"\g<1>{new_base}\g<2>",
            text,
        )
        total += count
    return text, total


def _base_version(version: str) -> str:
    """The release without its registry ``~revision``."""
    return version.split("~", 1)[0]


def rewrite_platformio(text: str, name: str, old: str, new: str) -> tuple[str, int]:
    """Rewrite ``ns/name@old`` library pins.

    The PlatformIO registry differs in case and has no ``~revision``
    re-uploads, so a revision-only bump leaves the file alone.
    """
    old_base, new_base = _base_version(old), _base_version(new)
    if old_base == new_base:
        return text, 0
    return re.subn(
        rf"(?im)^(\s*{re.escape(name)}@){re.escape(old_base)}(?=\s|$)",
        rf"\g<1>{new_base}",
        text,
    )


def plan_bump(root: Path, name: str, new: str) -> list[tuple[Path, str]]:
    """The files and their new contents for bumping ``name`` to ``new``.

    Nothing is written, so a pin the script cannot handle raises without
    touching the checkout.
    """
    manifest_path = root / MANIFEST
    manifest_text = manifest_path.read_text(encoding="utf-8")
    try:
        old = manifest_pins(manifest_text)[name]
    except KeyError:
        raise BumpError(f"{name}: not pinned in {MANIFEST}") from None
    if old == new:
        raise BumpError(f"{name}: already at {new}")

    writes: list[tuple[Path, str]] = [
        (manifest_path, rewrite_manifest(manifest_text, name, old, new))
    ]
    for path in sorted((root / COMPONENTS_DIR).rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if f'"{name}"' not in text:
            continue
        rewritten, count = rewrite_python(text, name, old, new)
        if count == 0:
            raise BumpError(
                f"{name}: {path.relative_to(root)} references the component but "
                f"no pin at {old} was recognised"
            )
        writes.append((path, rewritten))

    platformio_path = root / PLATFORMIO_INI
    if platformio_path.is_file():
        text = platformio_path.read_text(encoding="utf-8")
        rewritten, count = rewrite_platformio(text, name, old, new)
        if count:
            writes.append((platformio_path, rewritten))

    return writes


def bump(root: Path, name: str, new: str) -> list[Path]:
    """Rewrite every copy of the pin for ``name``; returns the changed files."""
    writes = plan_bump(root, name, new)
    for path, text in writes:
        path.write_text(text, encoding="utf-8")
    return [path.relative_to(root) for path, _ in writes]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="repository checkout to edit"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser(
        "list", help="print outdated pins as JSON on stdout"
    )
    list_parser.add_argument(
        "names", nargs="*", help="only consider these components (default: all)"
    )

    bump_parser = commands.add_parser("bump", help="rewrite the pins of one component")
    bump_parser.add_argument("name", help="component, e.g. espressif/mdns")
    bump_parser.add_argument("version", help="new version, e.g. 1.14.1")

    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            outdated = find_outdated(
                args.root, set(args.names) or None, fetch=fetch_json
            )
            for item in outdated:
                print(f"{item.name}: {item.current} -> {item.latest}", file=sys.stderr)
            json.dump(
                [
                    {
                        "name": item.name,
                        "current": item.current,
                        "latest": item.latest,
                        "url": item.url,
                        "changelog": item.changelog,
                    }
                    for item in outdated
                ],
                sys.stdout,
            )
            print()
        else:
            for path in bump(args.root, args.name, args.version):
                print(f"updated {path}")
    except BumpError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
