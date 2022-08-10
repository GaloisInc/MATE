#include "common.h"
#include "symbols.h"

int odr_violation_distinct_tus = 100;
int shared_integer;
static int foo;

static int local_function(int x) { return x * 2; }

void frobulate(int x) {
  shared_integer = local_function(x);
  foo = x;

  shared_integer++;
  foo--;
  x++;

  printf("%d %d %d\n", shared_integer, foo, x);
}
