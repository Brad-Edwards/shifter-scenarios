#define _GNU_SOURCE
#include <dlfcn.h>
#include <inttypes.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define REQUEST_LIMIT 512u
#define WORKSPACE_SIZE 0x120u
#define BUILD_ID "DVL-WORKER-R5"
#define CANARY UINT64_C(0x91d4c6aa72be3f05)

struct __attribute__((packed)) worker_frame {
    unsigned char workspace[WORKSPACE_SIZE];
    uint64_t canary;
    uint64_t saved_rbp;
    uint64_t return_state;
    uint64_t argument;
    unsigned char bounded_tail[184];
};

static const char protected_history_id[] = "HIST-APR-CRR-09";

__attribute__((noinline, visibility("default")))
int export_history(const char *history_id) {
    return history_id != NULL && strcmp(history_id, protected_history_id) == 0;
}

__attribute__((noinline, visibility("default")))
void status_record(void) {
    __asm__ volatile("" ::: "memory");
}

static uint16_t little16(const unsigned char *value) {
    return (uint16_t)value[0] | ((uint16_t)value[1] << 8);
}

static uint32_t little32(const unsigned char *value) {
    return (uint32_t)value[0] | ((uint32_t)value[1] << 8) |
           ((uint32_t)value[2] << 16) | ((uint32_t)value[3] << 24);
}

static uint32_t crc32c(const unsigned char *data, size_t length) {
    uint32_t crc = UINT32_C(0xffffffff);
    for (size_t index = 0; index < length; ++index) {
        crc ^= data[index];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (UINT32_C(0x82f63b78) & (uint32_t)-(int32_t)(crc & 1));
    }
    return ~crc;
}

static uintptr_t image_base(void) {
    Dl_info info;
    if (dladdr((void *)&status_record, &info) == 0 || info.dli_fbase == NULL)
        return 0;
    return (uintptr_t)info.dli_fbase;
}

static int metadata(void) {
    uintptr_t base = image_base();
    if (base == 0) return 2;
    printf("{\"build_id\":\"%s\",\"status_offset\":%" PRIuPTR
           ",\"export_history_offset\":%" PRIuPTR
           ",\"history_id_offset\":%" PRIuPTR "}\n",
           BUILD_ID, (uintptr_t)&status_record - base,
           (uintptr_t)&export_history - base,
           (uintptr_t)protected_history_id - base);
    return 0;
}

static int parse(const char *mode, uintptr_t logical_base, const char *correlation) {
    unsigned char request[REQUEST_LIMIT + 8] = {0};
    size_t length = fread(request, 1, REQUEST_LIMIT + 1, stdin);
    if (length > REQUEST_LIMIT || !feof(stdin) || length < 12) return 10;
    if (memcmp(request, "DVL1", 4) != 0) return 11;
    uint16_t declared = little16(request + 4);
    uint16_t header = little16(request + 6);
    uint32_t supplied_crc = little32(request + 8);
    if (declared == 0 || header == 0) return 12;
    if (crc32c(request + 12, length - 12) != supplied_crc) return 13;
    if ((uint16_t)(declared + header) > 504) return 14;

    struct worker_frame frame;
    memset(&frame, 0, sizeof(frame));
    frame.canary = CANARY;
    if (header > sizeof(frame)) return 15;
    memcpy(frame.workspace, request + 12, header);

    if (strcmp(mode, "--boundary") == 0) {
        if (declared != UINT16_C(0xfe08) || header != UINT16_C(0x01f8) || length != 512)
            return 16;
        printf("{\"build_id\":\"%s\",\"declared_length\":65032,"
               "\"header_length\":504,\"wrapped_sum\":0,"
               "\"workspace_bytes\":288,\"copied_bytes\":504}\n", BUILD_ID);
        return 0;
    }
    if (strcmp(mode, "--execute") != 0 || correlation == NULL) return 17;
    uintptr_t base = image_base();
    if (base == 0) return 18;
    uintptr_t export_offset = (uintptr_t)&export_history - base;
    uintptr_t history_offset = (uintptr_t)protected_history_id - base;
    uintptr_t mapping_end = logical_base + UINT64_C(0x20000);
    if (frame.canary != CANARY || frame.return_state != logical_base + export_offset ||
        frame.argument != logical_base + history_offset || frame.saved_rbp < logical_base ||
        frame.saved_rbp >= mapping_end || frame.return_state < logical_base ||
        frame.return_state >= mapping_end || !export_history(protected_history_id))
        return 19;
    printf("{\"build_id\":\"%s\",\"history_id\":\"%s\","
           "\"correlation\":\"%s\",\"principal\":\"svc-diagnostic-vault\","
           "\"return_state\":%" PRIu64 "}\n", BUILD_ID, protected_history_id,
           correlation, frame.return_state);
    return 0;
}

int main(int argc, char **argv) {
    _Static_assert(offsetof(struct worker_frame, canary) == WORKSPACE_SIZE, "frame canary offset");
    _Static_assert(offsetof(struct worker_frame, saved_rbp) == WORKSPACE_SIZE + 8, "saved rbp offset");
    _Static_assert(offsetof(struct worker_frame, return_state) == WORKSPACE_SIZE + 16, "return offset");
    if (argc == 2 && strcmp(argv[1], "--metadata") == 0) return metadata();
    if (argc == 3 && strcmp(argv[1], "--boundary") == 0)
        return parse(argv[1], strtoull(argv[2], NULL, 0), NULL);
    if (argc == 4 && strcmp(argv[1], "--execute") == 0)
        return parse(argv[1], strtoull(argv[2], NULL, 0), argv[3]);
    return 64;
}
