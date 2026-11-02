#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

__attribute__((noinline))
static uint64_t selector(uint64_t request_id, uint64_t epoch_bucket) {
  uint64_t x = request_id ^ UINT64_C(0x9e3779b97f4a7c15);
  uint64_t y = epoch_bucket ^ UINT64_C(0xbf58476d1ce4e5b9);
  x ^= x << 23;
  uint64_t next = x ^ y ^ (x >> 17) ^ (y >> 26);
  return next + y;
}

int main(int argc, char **argv) {
  if (argc != 3) {
    fprintf(stderr, "usage: %s REQUEST_ID_HEX EPOCH_BUCKET\n", argv[0]);
    return 64;
  }
  char *end = NULL;
  uint64_t request_id = strtoull(argv[1], &end, 16);
  if (!end || *end != '\0') return 65;
  end = NULL;
  uint64_t epoch_bucket = strtoull(argv[2], &end, 10);
  if (!end || *end != '\0') return 65;
  printf("%" PRIu64 "\n", selector(request_id, epoch_bucket));
  return 0;
}
