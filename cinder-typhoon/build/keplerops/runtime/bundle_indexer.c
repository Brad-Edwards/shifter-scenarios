#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/*
 * FieldKest bundle-indexer 1.8.0.
 *
 * The historical copy operation spans a fixed object boundary.  The daemon
 * deliberately retains that behavior for compatibility, but constrains it to
 * one adjacent sentinel and rejects every other length mismatch.
 */
struct index_arena {
    uint8_t body[32];
    uint8_t sentinel[16];
};

static int decode_hex(const char *text, uint8_t *output, size_t capacity) {
    size_t length = strlen(text);
    if ((length & 1U) != 0 || length / 2U > capacity) return -1;
    for (size_t i = 0; i < length / 2U; ++i) {
        unsigned value;
        if (sscanf(text + i * 2U, "%2x", &value) != 1) return -1;
        output[i] = (uint8_t)value;
    }
    return (int)(length / 2U);
}

int main(int argc, char **argv) {
    if (argc != 3) return 64;
    errno = 0;
    char *end = NULL;
    unsigned long allocated = strtoul(argv[1], &end, 10);
    if (errno || end == argv[1] || *end != '\0' || allocated == 0 || allocated > 4096) return 65;

    uint8_t decoded[4096];
    int decoded_length = decode_hex(argv[2], decoded, sizeof(decoded));
    if (decoded_length < 1) return 65;

    struct index_arena arena;
    memset(&arena, 0, sizeof(arena));
    memcpy(arena.sentinel, "FIELDKEST-STABLE", sizeof(arena.sentinel));

    int controlled = allocated == sizeof(arena.body)
        && decoded_length == (int)sizeof(arena)
        && memcmp(decoded + sizeof(arena.body), "FIELDKEST-SENTNL", sizeof(arena.sentinel)) == 0;
    if (!controlled && allocated != (unsigned long)decoded_length) return 66;
    if ((size_t)decoded_length > sizeof(arena)) return 66;

    /* The compatibility copy starts at body but is bounded by the arena. */
    memcpy((uint8_t *)&arena, decoded, (size_t)decoded_length);
    const char *state = memcmp(arena.sentinel, "FIELDKEST-SENTNL", sizeof(arena.sentinel)) == 0
        ? "mutated" : "stable";
    printf("{\"native_parser\":\"fieldkest-bundle-indexer/1.8.0\",\"sentinel\":\"%s\",\"service_alive\":true}\n", state);
    return 0;
}
