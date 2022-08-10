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

    __asm__("movq $0x0, %rax\n"
            "subq %rax, %rax\n"
            "jz foo\n"
            "foo:\n");

    x = 100;
    printf("%d\n", COINFLIP() + x);

    __asm__("movq $0x0, %rbx\n"
            "subq %rbx, %rbx\n"
            "jz bar\n"
            "bar:\n");
  }
  return 0;
}
