// A minimal user-mode WPP provider, used to produce the WPP fixture and to
// exercise WPP decoding end to end in CI.
//
// WPP events carry no schema. The format strings live in a .tmf generated from
// this binary's PDB, or in that PDB directly, and without one TDH will only ever
// say "No Format Information found".
//
// Note the trace GUID that names the .tmf is derived by WPP from this file's
// full path, so a build in a different directory produces a different GUID and
// cannot decode a capture made elsewhere. Anything verifying the PDB route has
// to build and capture in the same place.

#include <windows.h>
#include <stdio.h>

// {A9B4C1D2-3E5F-4A6B-8C7D-9E0F1A2B3C4D}
#define WPP_CONTROL_GUIDS                                              \
    WPP_DEFINE_CONTROL_GUID(                                           \
        PyEtwKitWppTest,                                               \
        (A9B4C1D2, 3E5F, 4A6B, 8C7D, 9E0F1A2B3C4D),                    \
        WPP_DEFINE_BIT(TEST_ALL))

#include "wpptest.tmh"

int main(void)
{
    // User-mode WPP takes an application name here; the kernel-mode form does not.
    WPP_INIT_TRACING(L"PyEtwKitWppTest");

    for (int i = 0; i < 3; i++) {
        DoTraceMessage(TEST_ALL,
                       "wpp probe seq=%d name=%s value=0x%x",
                       i, "core-state", 0x50C0 + i);
    }

    WPP_CLEANUP();
    printf("emitted 3 WPP events\n");
    return 0;
}
