"""Auto-loaded shim for ESP-IDF's component-manager subprocesses.

``esphome.espidf.framework._install_libsodium_shim`` copies this file into the
ESP-IDF penv's ``site-packages`` as ``sitecustomize.py`` when the penv is
(re)installed. Python's ``site`` machinery imports a ``sitecustomize`` module
from ``site-packages`` at interpreter startup, so this file runs in ``idf.py``
*and* in the ``idf_component_manager`` subprocess that CMake spawns during the
configure step -- which is exactly where dependency resolution (and the
collision) happens. Both run under the penv interpreter, so a single copy
covers them all.

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
* The shim never raises: any failure is logged and the build proceeds
  unpatched (and would then hit the original collision, which is the honest
  signal that the patch stopped applying).
"""

import sys

# Espressif's libsodium under any spelling (default-namespace "libsodium"
# normalizes to "espressif/libsodium"). esphome's fork ("esphome/libsodium")
# is intentionally not matched.
_ESPRESSIF_LIBSODIUM = frozenset({"espressif/libsodium", "libsodium"})

try:
    # idf_component_tools only exists in the ESP-IDF penv, not esphome's venv.
    from idf_component_tools.manifest import models  # pylint: disable=import-error

    _orig_raw_requirements = models.Manifest.raw_requirements.fget

    def _raw_requirements(self):
        reqs = _orig_raw_requirements(self)
        kept = [
            r
            for r in reqs
            if str(getattr(r, "name", "") or "").replace("__", "/")
            not in _ESPRESSIF_LIBSODIUM
        ]
        if len(kept) != len(reqs):
            sys.stderr.write(
                "NOTICE: esphome stripped espressif/libsodium from manifest "
                f"'{getattr(self, 'name', '?')}'\n"
            )
        return kept

    models.Manifest.raw_requirements = property(_raw_requirements)
except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
    sys.stderr.write(f"esphome libsodium-strip shim failed to apply: {exc!r}\n")
