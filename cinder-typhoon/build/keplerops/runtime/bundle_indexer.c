/* FieldKest bundle-indexer 2.0.0.
 *
 * Parses .fki release-bundle archives and indexes their entries
 * into the runtime object graph.
 *
 * Usage: fieldkest-bundle-indexer <bundle_hex>
 *
 * Archive format:
 *   magic[4]        "FKI\x01"
 *   alloc_entries   uint16_le  declared allocation hint
 *   index_entries   uint16_le  number of entries in this bundle
 *   entry_data[]    index_entries * 8 bytes of entry records
 *
 * Returns JSON on stdout; non-zero exit on format error.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct index_arena {
    uint8_t body[64];
    uint8_t sentinel[16];
};

static int hex_decode(const char *src, uint8_t *dst, size_t cap) {
    size_t n = strlen(src);
    if (n & 1U || n / 2U > cap) return -1;
    for (size_t i = 0; i < n / 2U; ++i) {
        unsigned v;
        if (sscanf(src + i * 2U, "%2x", &v) != 1) return -1;
        dst[i] = (uint8_t)v;
    }
    return (int)(n / 2U);
}

#pragma pack(push, 1)
struct fki_header {
    char     magic[4];
    uint16_t alloc_entries;
    uint16_t index_entries;
};
#pragma pack(pop)

int main(int argc, char **argv) {
    if (argc != 2) return 64;

    uint8_t buf[4096];
    int buflen = hex_decode(argv[1], buf, sizeof(buf));
    if (buflen < (int)sizeof(struct fki_header)) return 65;

    const struct fki_header *hdr = (const struct fki_header *)buf;
    if (memcmp(hdr->magic, "FKI\x01", 4) != 0) return 65;

    uint16_t ae = hdr->alloc_entries;
    uint16_t ie = hdr->index_entries;
    if (ie == 0 || ie > 512) return 65;

    size_t datalen = (size_t)ie * 8U;

    /* Bounds check: the declared allocation hint (ae) is treated as an
     * additional byte allowance beyond the arena body.  When ae is
     * supplied as an entry count (not bytes), the check admits bundles
     * whose entry data extends into the adjacent sentinel region. */
    if (datalen > sizeof(struct index_arena) + (size_t)ae) return 66;
    if (buflen < (int)sizeof(struct fki_header) + (int)datalen) return 65;

    struct index_arena arena;
    memset(&arena, 0, sizeof(arena));
    memcpy(arena.body, buf + sizeof(struct fki_header), datalen);

    const char *state = (arena.sentinel[0] != 0x00) ? "mutated" : "stable";
    printf("{\"native_parser\":\"fieldkest-bundle-indexer/2.0.0\","
           "\"sentinel\":\"%s\",\"service_alive\":true}\n", state);
    return 0;
}
