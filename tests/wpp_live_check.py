"""Verify WPP decoding against a freshly built provider, including the PDB route.

Run by CI after ``tests/fixtures/create_wpp_etl.ps1`` has built the provider and
captured its events. Not a pytest module on purpose: the PDB route cannot be
covered by the committed fixture, because WPP derives the trace GUID from the
source file's full path, so the PDB must come from the same build that produced
the capture. Expressing that as a test that skips unless CI set some environment
variables would just be a skip nobody notices.

Exits non-zero on the first disagreement.

    python tests/wpp_live_check.py <wpp.etl> <tmf-dir> <wpptest.pdb>
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyetwkit._core as core

EXPECTED = [
    "wpp probe seq=0 name=core-state value=0x50c0",
    "wpp probe seq=1 name=core-state value=0x50c1",
    "wpp probe seq=2 name=core-state value=0x50c2",
]

PLACEHOLDER = "No Format Information found"


def clear() -> None:
    core.set_wpp_tmf_search_path(None)
    core.set_wpp_tmf_file(None)
    core.set_wpp_pdb_path(None)


def messages(etl: str) -> list[str]:
    return [
        e.properties["FormattedString"]
        for e in core.EtlReader(etl).read_all()
        if "FormattedString" in e.properties
    ]


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    etl, tmf_dir, pdb = sys.argv[1:4]

    tmf_files = sorted(Path(tmf_dir).glob("*.tmf"))
    if not tmf_files:
        print(f"FAIL: no .tmf produced in {tmf_dir}")
        return 1
    print(f"etl={etl}\ntmf={tmf_files[0]}\npdb={pdb}\n")

    failures = 0

    clear()
    got = messages(etl)
    if not got:
        print("FAIL: the capture carried no WPP events at all")
        return 1
    if not all(PLACEHOLDER in m for m in got):
        print(f"FAIL: expected placeholders with no source configured, got {got}")
        failures += 1
    else:
        print(f"ok   no source configured -> {len(got)} placeholders")

    for label, setup in [
        ("tmf search path", lambda: core.set_wpp_tmf_search_path(tmf_dir)),
        ("tmf file", lambda: core.set_wpp_tmf_file(str(tmf_files[0]))),
        ("pdb path", lambda: core.set_wpp_pdb_path(pdb)),
    ]:
        clear()
        setup()
        got = messages(etl)
        if got == EXPECTED:
            print(f"ok   {label} -> decoded")
        else:
            print(f"FAIL: {label} produced {got}, expected {EXPECTED}")
            failures += 1

    clear()
    if failures:
        print(f"\n{failures} check(s) failed")
        return 1
    print("\nall WPP decoding routes verified, including the PDB route")
    return 0


if __name__ == "__main__":
    sys.exit(main())
