#include <algorithm>
#include <cstdlib>
#include <ctime>
#include <stdio.h>

int no_args_int_return() { return 3; }

int bar(int x, int y) {
  if (y < 4) {
    return y;
  }
  return x;
}

int foo() {
  int x = no_args_int_return();
  int y = no_args_int_return();
  int result0 = bar(x, y);
  int w = x * 2;
  int z = y / 2;
  int result1 = bar(w, z);
  return std::min(result0, result1);
}

int main() { return foo(); }
