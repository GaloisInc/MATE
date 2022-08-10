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
  int x = COINFLIP();

  if (x) {
    x = 1000;

    if (x && COINFLIP()) {
      printf("foo\n");
    }

    x = 0;

    // NOTE(ww): This doesn't do anything interesting,
    // and probably crashes if you actually run it.
    __asm__("mov $0x0, %rax\n"
            "sub %rax, %rax\n"
            "jz foo\n"
            "bar:\n"
            "pushq %rax\n"
            "ret\n"
            "foo:\n"
            "jmp bar\n");
  }
  return 0;
}
