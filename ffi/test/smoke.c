// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Host smoke test: links the GMATWiz C FFI and calls into the shared Anki
// engine. Proves the C ABI works at runtime without Xcode/iOS. The same calls
// will be made from Swift on iOS once Xcode is installed.

#include <stdio.h>
#include "gmatwiz_ffi.h"

int main(void) {
    char *hello = gmatwiz_hello();
    char *hash = gmatwiz_buildhash();
    printf("gmatwiz_hello=%s\n", hello ? hello : "(null)");
    printf("gmatwiz_buildhash=%s\n", hash ? hash : "(null)");
    gmatwiz_string_free(hello);
    gmatwiz_string_free(hash);
    return 0;
}
