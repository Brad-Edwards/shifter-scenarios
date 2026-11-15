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
 * The arena is backed by a persistent shared region.  On every request the
 * binary reads the current 128-byte region into a local buffer (capturing
 * any state the service wrote since the last request), copies the bundle
 * entry data into the region (updating it), and returns data_hex of the
 * local read buffer up to datalen bytes as an ordinary part of the response.
 * The sentinel is at bytes 64-79 of the region; the runtime descriptor
 * occupies bytes 80-127 and is written by the service when the first
 * mutation is recorded.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ARENA_SHM_PATH "/var/lib/fieldkest-indexer/arena.shm"
#define ARENA_SIZE 512

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
    /* Bounds check uses the arena struct size (body+sentinel=80), not ARENA_SIZE.
     * To reach the descriptor at bytes 80-511 the participant must supply
     * alloc_entries >= ARENA_SIZE - sizeof(struct index_arena) = 432. */
    if (datalen > sizeof(struct index_arena) + (size_t)ae) return 66;
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
     * read_buf captured the arena state BEFORE the write, so bytes 80-127
     * reflect service-written descriptor data when K04.1 preceded this call.
     * When datalen=128 (ie=16, ae=48) the descriptor at bytes 80-127 is
     * included; bytes 64-79 of the read buffer show the pre-write sentinel. */
    printf("{\"native_parser\":\"fieldkest-bundle-indexer/2.0.0\","
           "\"sentinel\":\"%s\",\"service_alive\":true,\"data_hex\":\"", state);
    for (size_t i = 0; i < datalen; ++i) {
        printf("%02x", read_buf[i]);
    }
    printf("\"}\n");
    return 0;
}
