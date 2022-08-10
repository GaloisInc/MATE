#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void __attribute__((noinline)) printi(int i) { printf("%i", i); }

const int DIGITS[] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};

int main() {
  int x = getc(stdin);
  int z = x + 2;
  printi(z); // thin dataflow
  if (x < sizeof(DIGITS)) {
    printi(DIGITS[x]); // non-thin dataflow
  }
  return 0;
}
