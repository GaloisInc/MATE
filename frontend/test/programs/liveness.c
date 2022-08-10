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

typedef struct {
  char a[192];
  int b[100];
} foo;

int main(int argc, char const *argv[]) {
  char x[128] = "hello!";
  printf("%s\n", x);

  x[5] = '.';
  printf("%s\n", x);

  if (COINFLIP()) {
    char y[512] = "coinflip";
    printf("%s\n", y);
  }

  {
    char z[rand() % 100 + 1];
    z[0] = 'A';
    printf("value at z[0]: %c\n", z[0]);
  }

  char *a1;
  if (COINFLIP()) {
    char a[32] = "coinFLIP";

    a[16] = 1;
    a[17] = 2;
    a[18] = 3;

    int x;
    switch (COINFLIP()) {
    case 0: {
      x = a[16];
      break;
    }
    case 1: {
      x = a[17];
      break;
    }
    default: {
      x = a[18];
      break;
    }
    }
    printf("%d\n", x);

    a1 = a;
  } else {
    char a[64] = "COINflip";
    a1 = a;
  }

  printf("%s\n", a1);

  foo a = {};
  memcpy(a.a, "hello", 5);
  a.b[0] = 100;
  {
    foo b;
    memcpy(b.a, a.a, 5);
    b.b[1] = a.b[0] + 1;
    printf("b.a=%s b.b[0]=%d\n", b.a, b.b[0]);
  }

  return 0;
}
