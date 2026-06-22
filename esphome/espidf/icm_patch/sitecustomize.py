"""Auto-loaded shim for ESP-IDF's component-manager subprocesses.

This directory is prepended to ``PYTHONPATH`` by
``esphome.espidf.framework.get_framework_env`` for every ``idf.py`` run.
Python's ``site`` machinery imports a ``sitecustomize`` module found anywhere
on ``sys.path`` at interpreter startup, so this file runs in ``idf.py`` *and*
in the ``idf_component_manager`` subprocess that CMake spawns during the
configure step -- which is exactly where dependency resolution (and the
collision) happens. Env (and therefore ``PYTHONPATH``) is inherited down the
idf.py -> cmake -> component-manager process chain, so a single injection
point covers them all.

What it does
------------
Strips arduino-esp32's unused ``espressif/libsodium`` dependency. The ESP-IDF
component manager refuses two managed components that share the ``libsodium``
short name -- ``espressif__libsodium`` (pulled by arduino-esp32) vs
``esphome__libsodium`` (pulled by noise-c) -- and raises::

    Requirement libsodium and requirement libsodium are both added as
    idf_managed_components. Can't decide which one to pick.

arduino-esp32 declares libsodium as ``require: public`` in its
``idf_component.yml`` but never calls it (no ``sodium.h`` include anywhere in
the Arduino core or its libraries), and ESPHome already ships it as an empty
stub today -- so removing it from the dependency graph is safe and leaves
esphome's libsodium fork as the sole ``libsodium`` component.

Prototype caveats
-----------------
* Patches a private ``idf_component_tools`` property (``Manifest.raw_requirements``).
  Re-verify on every ESP-IDF / idf-component-manager bump. Developed against
  idf_component_tools 3.0.3 (ESP-IDF 5.5.4).
* Set ``ESPHOME_IDF_KEEP_ESPRESSIF_LIBSODIUM=1`` to disable the strip (e.g. to
  reproduce the collision) without unwiring the PYTHONPATH injection.
* The shim never raises: any failure is logged and the build proceeds
  unpatched (and would then hit the original collision, which is the honest
  signal that the patch stopped applying).
"""

import os
import sys

# Names that all refer to Espressif's libsodium (default-namespace "libsodium"
# normalizes to "espressif/libsodium"). esphome's fork is "esphome/libsodium"
# and is intentionally NOT matched here.
_DROP_NAMES = frozenset({"espressif/libsodium", "libsodium"})


def _is_espressif_libsodium(name: object) -> bool:
    return (str(name) if name else "").replace("__", "/") in _DROP_NAMES


def _install_patch() -> None:
    from idf_component_tools.manifest import models

    orig_raw_requirements = models.Manifest.raw_requirements.fget

    def raw_requirements(self):
        reqs = orig_raw_requirements(self)
        kept = [
            r for r in reqs if not _is_espressif_libsodium(getattr(r, "name", None))
        ]
        if len(kept) != len(reqs):
            sys.stderr.write(
                "NOTICE: esphome stripped espressif/libsodium from manifest "
                f"'{getattr(self, 'name', '?')}'\n"
            )
        return kept

    models.Manifest.raw_requirements = property(raw_requirements)


if os.environ.get("ESPHOME_IDF_KEEP_ESPRESSIF_LIBSODIUM") != "1":
    try:
        _install_patch()
    except Exception as exc:  # noqa: BLE001 - never break the build over the shim
        sys.stderr.write(f"esphome libsodium-strip shim failed to apply: {exc!r}\n")
