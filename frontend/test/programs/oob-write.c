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
  uint32_t x, y = 0;
  uint64_t src = 0xFF00FF00FF00FF00;

  memcpy(&x, &src, sizeof(src));
  printf("x=0x%08x, y=0x%08x\n", x, y);
  return 0;
}
