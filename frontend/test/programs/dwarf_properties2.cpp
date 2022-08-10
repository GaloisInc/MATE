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

struct BaseStruct1 {
  int x;
};

struct BaseStruct2 {
  int x2;
};

struct ChildStruct1 : BaseStruct1 {
  int y;
};

struct ChildStruct2 : BaseStruct1, BaseStruct2 {
  float junk;
};

struct ChildStruct3 : ChildStruct1, ChildStruct2 {
  double more_junk;
};

int main(int argc, char const *argv[]) {
  ChildStruct1 child1;
  ChildStruct2 child2;
  ChildStruct3 child3;

  if (COINFLIP()) {
    child2.x = COINFLIP();
    child2.x2 = COINFLIP();
    child1.y = COINFLIP() + child2.x + child2.x2;
    child3.more_junk = COINFLIP() + 0.1;
  } else {
    child2.junk = COINFLIP() + (3.14 * COINFLIP());
    child1.x = COINFLIP();
    if (child1.x && COINFLIP()) {
      child1.x = 100;
    }
    child1.y = child1.x + child2.junk + COINFLIP();
    child3.more_junk = COINFLIP() + 0.2;
  }

  printf("child1.y: %d, child3.more_junk: %f\n", child1.y, child3.more_junk);
  return 0;
}
