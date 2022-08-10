#include "common.h"
#include "symbols.h"

int odr_violation_distinct_tus;
static int foo;

static float local_function(float x) {
  if (COINFLIP()) {
    return x * 3.14;
  } else {
    return x * 1;
  }
}

int main(int argc, char const *argv[]) {
  foo = 0;
  frobulate(foo);
  frobulate(COINFLIP());
  frobulate(COINFLIP());

  float bar = 3.14;
  printf("%f\n", local_function(bar));
  return 0;
}
