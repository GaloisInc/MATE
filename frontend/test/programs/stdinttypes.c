#include <fcntl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __cplusplus
#include <exception>
#include <functional>
#include <iostream>
#include <numeric>
#include <string>
#include <system_error>
#include <vector>
#endif

#define COINFLIP() (rand() % 2)

int main(int argc, char const *argv[]) {
  uint8_t unsigned_8_bits;
  int8_t signed_8_bits;

  unsigned_8_bits = COINFLIP();
  signed_8_bits = COINFLIP();

  uint32_t unsigned_32_bits = unsigned_8_bits + signed_8_bits + COINFLIP();

  if (COINFLIP()) {
    printf("%" PRIu32 "\n", unsigned_32_bits);
  } else {
    int64_t signed_64_bits = -unsigned_32_bits;
    printf("%" PRId64 "\n", signed_64_bits);
  }

  return 0;
}
