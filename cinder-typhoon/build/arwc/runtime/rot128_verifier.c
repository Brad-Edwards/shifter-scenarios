#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "rot128_expected.h"

typedef unsigned __int128 u128;

static u128 rotl128(u128 value, unsigned count) {
    return (value << count) | (value >> (128U - count));
}

static u128 little_u128(const unsigned char block[16]) {
    u128 value = 0;
    for (int index = 15; index >= 0; --index) value = (value << 8) | block[index];
    return value;
}

static u128 verifier(const unsigned char *data, size_t length) {
    const u128 iv = ((u128)UINT64_C(0x6a09e667f3bcc908) << 64) | UINT64_C(0xbb67ae8584caa73b);
    size_t padded = ((length + 1U + 15U) / 16U) * 16U;
    unsigned char *material = calloc(padded, 1U);
    if (material == NULL) exit(2);
    memcpy(material, data, length);
    material[length] = 0x80;
    u128 state = iv;
    for (size_t offset = 0; offset < padded; offset += 16U) {
        u128 block = little_u128(material + offset);
        state = rotl128(state, 17U) ^ block ^ rotl128(block, 41U);
    }
    free(material);
    return state ^ rotl128(state, 29U) ^ (u128)length;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *input = fopen(argv[1], "rb");
    if (input == NULL) return 2;
    if (fseek(input, 0, SEEK_END) != 0) return 2;
    long extent = ftell(input);
    if (extent < 0 || extent > 65536 || fseek(input, 0, SEEK_SET) != 0) return 2;
    unsigned char *data = malloc((size_t)extent + 1U);
    if (data == NULL || fread(data, 1U, (size_t)extent, input) != (size_t)extent) return 2;
    fclose(input);
    u128 digest = verifier(data, (size_t)extent);
    free(data);
    uint64_t high = (uint64_t)(digest >> 64), low = (uint64_t)digest;
    u128 expected = ((u128)ROT128_EXPECTED_HI << 64) | ROT128_EXPECTED_LO;
    printf("{\"digest\":\"%016" PRIx64 "%016" PRIx64 "\",\"decision\":\"%s\"}\n",
           high, low, digest == expected ? "accepted" : "rejected");
    return 0;
}
