#include <stdio.h>

void __attribute__((noinline)) printi(int i) { printf("%i", i); }

typedef void fun_t(int argc, char **argv);

int main(int argc, char **argv) {
  ((fun_t *)printi)(argc, argv);
  return 0;
}
