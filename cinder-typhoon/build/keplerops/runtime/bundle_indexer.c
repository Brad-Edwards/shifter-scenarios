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
 *
 * The arena is backed by a persistent shared region of ARENA_SIZE bytes.
 * On every request the binary reads the full region into a local buffer
 * (capturing any state the service wrote since the last request), copies the
 * bundle entry data into the region (updating it), and returns data_hex of
 * the local read buffer up to datalen bytes as an ordinary part of the response.
 *
 * Arena layout:
 *   bytes   0-63   body          (normal index entries)
 *   bytes  64-79   sentinel      (non-zero after first mutation)
 *   bytes  80-511  descriptor    (service writes runtime descriptor at K04.1)
 *   bytes 512-543  exception_value    (32 bytes, NUL-padded ASCII)
 *   bytes 544-575  exception_integrity (32 bytes, keyed digest)
 *   bytes 576-1023 reserved
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ARENA_SHM_PATH "/var/lib/fieldkest-indexer/arena.shm"
#define ARENA_SIZE 1024
/* index_arena = body[64] + sentinel[16]; descriptor occupies bytes 80-511;
 * exception-state region occupies bytes 512-575 */
#define INDEX_ARENA_SIZE 80

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
    /* Bounds check uses INDEX_ARENA_SIZE (body+sentinel=80), not ARENA_SIZE.
     * To reach the descriptor at bytes 80-511 the participant must supply
     * alloc_entries >= ARENA_SIZE - INDEX_ARENA_SIZE = 432. */
    if (datalen > INDEX_ARENA_SIZE + (size_t)ae) return 66;
    if (buflen < (int)sizeof(struct fki_header) + (int)datalen) return 65;

    /* Read the current arena region before writing.  This captures state
     * the service may have placed at bytes 80-511 since the last request. */
    uint8_t read_buf[ARENA_SIZE];
    memset(read_buf, 0, ARENA_SIZE);
    int fd = open(ARENA_SHM_PATH, O_RDWR | O_CREAT, 0600);
    if (fd >= 0) {
        /* Extend to full size if needed */
        off_t cur = lseek(fd, 0, SEEK_END);
        if (cur < ARENA_SIZE) {
            uint8_t zero = 0;
            for (off_t i = cur; i < ARENA_SIZE; ++i) write(fd, &zero, 1);
        }
        lseek(fd, 0, SEEK_SET);
        (void)read(fd, read_buf, ARENA_SIZE);

        /* Write the bundle entry data into the persistent region. */
        lseek(fd, 0, SEEK_SET);
        (void)write(fd, buf + sizeof(struct fki_header), datalen);
        close(fd);
    }

    /* Sentinel is at bytes 64-79.  Determine its state from the participant's
     * write (what will be at byte 64 after the memcpy), falling back to the
     * read buffer when the write does not reach the sentinel region. */
    uint8_t written_sentinel_byte = (datalen > 64)
        ? *(buf + sizeof(struct fki_header) + 64)
        : read_buf[64];
    const char *state = (written_sentinel_byte != 0x00) ? "mutated" : "stable";

    /* Emit data_hex of the read buffer up to datalen bytes.
     * read_buf captured the arena state BEFORE the write.  When datalen=512
     * (ie=64, ae=432) bytes 80-511 include the service-written descriptor.
     * When datalen=576 (ie=72, ae=496) bytes 512-575 also include the
     * exception-state region seeded by the service at K04.1 time. */
    printf("{\"native_parser\":\"fieldkest-bundle-indexer/2.0.0\","
           "\"sentinel\":\"%s\",\"service_alive\":true,\"data_hex\":\"", state);
    for (size_t i = 0; i < datalen; ++i) {
        printf("%02x", read_buf[i]);
    }
    printf("\"}\n");
    return 0;
}
