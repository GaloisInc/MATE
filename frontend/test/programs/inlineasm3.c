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
  __asm__("movq $0x3, %rax\n"
          "foo:\n"
          "subq $0x1, %rax\n"
          "jnz foo\n"
          "movq $0x6, %rax\n"
          "bar:\n"
          "subq $0x2, %rax\n"
          "jnz bar\n");
  return 0;
}
