#include <sodium.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const unsigned char public_key[32] = {
    0x0c,0xd5,0x41,0x56,0xdf,0x9b,0x68,0x57,0x09,0xd2,0x94,0x37,0x69,0x0e,0x94,0x2a,
    0xc3,0xf2,0x2e,0xfe,0x8d,0x22,0x8a,0x70,0x93,0xb5,0x49,0xd5,0x86,0x95,0x88,0x0d
};

static int decode_hex(const char *text, unsigned char *output, size_t length) {
  size_t written = 0;
  return sodium_hex2bin(output, length, text, strlen(text), NULL, &written, NULL) == 0 && written == length;
}

int main(int argc, char **argv) {
  if (sodium_init() < 0) return 70;
  if (argc == 2 && strcmp(argv[1], "--contract") == 0) {
    puts("DSIGN-CRR-R3 CRR25519-S Edwards25519 SHA-512(R||A||message) s=k+h*x");
    return 0;
  }
  if (argc != 4) {
    fprintf(stderr, "usage: %s message-hex R-hex s-hex\n", argv[0]);
    return 64;
  }
  size_t message_length = strlen(argv[1]) / 2;
  unsigned char *message = calloc(message_length ? message_length : 1, 1);
  unsigned char R[32], scalar[32], hash[64], h[32], left[32], hA[32], right[32];
  if (!message || !decode_hex(argv[1], message, message_length) ||
      !decode_hex(argv[2], R, sizeof R) || !decode_hex(argv[3], scalar, sizeof scalar) ||
      crypto_core_ed25519_is_valid_point(R) != 1 ||
      crypto_core_ed25519_is_valid_point(public_key) != 1) {
    free(message); return 65;
  }
  crypto_hash_sha512_state state;
  crypto_hash_sha512_init(&state);
  crypto_hash_sha512_update(&state, R, sizeof R);
  crypto_hash_sha512_update(&state, public_key, sizeof public_key);
  crypto_hash_sha512_update(&state, message, message_length);
  crypto_hash_sha512_final(&state, hash);
  crypto_core_ed25519_scalar_reduce(h, hash);
  if (crypto_scalarmult_ed25519_base_noclamp(left, scalar) != 0 ||
      crypto_scalarmult_ed25519_noclamp(hA, h, public_key) != 0 ||
      crypto_core_ed25519_add(right, R, hA) != 0) {
    free(message); return 65;
  }
  free(message);
  return sodium_memcmp(left, right, sizeof left) == 0 ? 0 : 1;
}
