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

int __attribute__((noinline)) coinflip() { return COINFLIP(); }

int __attribute__((noinline)) rand100() { return rand() % 100; }

int main(int argc, char const *argv[]) {
  srand(time(NULL));

  uint64_t rax;
  __asm__("call coinflip\n"
          "cmpq $0x0, %%rax\n"
          "jne foo\n"
          "call coinflip\n"
          "jmp end\n"
          "foo:\n"
          "call rand100\n"
          "end:"
          ""
          : "=a"(rax)::);

  printf("%lu\n", rax);

  return 0;
}
