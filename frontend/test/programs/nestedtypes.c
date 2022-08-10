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

struct nestedtypes {
  uint64_t field_1;
  uint64_t field_2;
  struct nested_1_type {
    uint8_t field_3;
    double *field_4;
  } nested_1;
  struct /* anonymous */ {
    char field_5[10];
    float field_6;
  } nested_2;
};

int main(int argc, char const *argv[]) {
  struct nestedtypes foo = {};

  if (COINFLIP()) {
    foo.nested_1.field_3 = COINFLIP() ? 1 : 0;
    foo.nested_2.field_6 = 100.0 + (COINFLIP() * COINFLIP() + 1);
  } else {
    foo.nested_1.field_3 = 0xBB;
    foo.nested_2.field_6 = (COINFLIP() + 1) * 3.14;
  }

  printf("field_3:%x field_6:%f\n", foo.nested_1.field_3, foo.nested_2.field_6);

  return 0;
}
