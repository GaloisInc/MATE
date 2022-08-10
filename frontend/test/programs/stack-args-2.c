#include <stdio.h>

int f(int, int, int, int, int, int, int, int, int, int, int, int, int, int)
    __attribute__((noinline));
int f(int a, int b, int c, int d, int e, int f, int g, int h, int i, int j,
      int k, int l, int m, int n) {
  printf("%d", a);
  printf("%d", b);
  printf("%d", c);
  printf("%d", d);
  printf("%d", e);
  printf("%d", f);
  printf("%d", g);
  printf("%d", h);
  printf("%d", i);
  printf("%d", j);
  printf("%d", k);
  printf("%d", l);
  printf("%d", m);
  printf("%d", n);
  return a;
}

int main(int argc, char *argv[] /* unused */) {
  return f(argc * 2, argc * 3, argc * 4, argc * 5, argc * 6, argc * 7, argc * 8,
           argc * 9, argc * 10, argc * 11, argc * 12, argc * 13, argc * 14,
           argc * 15);
}
