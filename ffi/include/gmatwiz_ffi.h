// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// C interface to the shared Anki Rust engine for GMATWiz.
// Used as the Swift bridging header on iOS so the phone app drives the SAME
// scheduler as the desktop app via the protobuf (service, method) interface.

#ifndef GMATWIZ_FFI_H
#define GMATWIZ_FFI_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct GmatwizBackend GmatwizBackend;
typedef struct GmatCollection GmatCollection;

// Returns the engine build hash. Free with gmatwiz_string_free.
char *gmatwiz_buildhash(void);

// Returns a smoke-test greeting proving FFI + engine linkage. Free with gmatwiz_string_free.
char *gmatwiz_hello(void);

// Frees a string returned by this library.
void gmatwiz_string_free(char *ptr);

// Opens a backend from a protobuf-encoded BackendInit message. Returns NULL on failure.
GmatwizBackend *gmatwiz_backend_open(const uint8_t *init_ptr, size_t init_len);

// Frees a backend opened with gmatwiz_backend_open.
void gmatwiz_backend_free(GmatwizBackend *handle);

// Runs a protobuf service method against the shared engine.
// Returns 0 on success, 1 on backend error, -1 on invalid arguments.
// On 0/1, *out_ptr / *out_len receive a buffer to free with gmatwiz_buffer_free.
int gmatwiz_backend_command(GmatwizBackend *handle,
                            uint32_t service,
                            uint32_t method,
                            const uint8_t *in_ptr,
                            size_t in_len,
                            uint8_t **out_ptr,
                            size_t *out_len);

// Frees a buffer returned by gmatwiz_backend_command.
void gmatwiz_buffer_free(uint8_t *ptr, size_t len);

// --- High-level GMATWiz collection API (iOS review session) ---

// Opens a collection at the given .anki2 path. Returns NULL on failure.
GmatCollection *gmatwiz_open_collection(const char *path);

// Frees a collection opened with gmatwiz_open_collection.
void gmatwiz_collection_free(GmatCollection *handle);

// Returns review state for `deck` (default "GMAT::Quant") as a JSON string
// {new, learning, review, card}. Free with gmatwiz_string_free.
char *gmatwiz_collection_state(GmatCollection *handle, const char *deck);

// Answers the current card via the real scheduler (correct => Good, else Again).
// Returns 0 on success, 1 on engine error, -1 on invalid arguments.
int gmatwiz_collection_answer(GmatCollection *handle, int64_t card_id, bool correct);

#ifdef __cplusplus
}
#endif

#endif // GMATWIZ_FFI_H
