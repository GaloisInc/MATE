#include <stdio.h>

int simple(int a) {
  if (a > 0) {
    if (a > 5) {
      return a - 3;
    }
    return a + 12;
  }
  return 32;
}

int loop(int a) {
  int b = 2;
  int c = 4;
  for (int i = 0; i < a; i++) {
    b += a;
    c *= b;
  }
  return c;
}

int infinite(int a) {
  int b = 32;
  while (2) {
    b *= a;
    if (b > 1000)
      break;
  }
  return 42;
}

int unreachable(int a) {
  int b = 32;
  while (2) {
    if (b < a)
      b *= a;
    if (b > 1000)
      return b;
  }
  return a + 2;
}

int diamond(int a) {
  if (a < 42) {
    return 0;
  }
  int b;
  if (a > 4) {
    b = 1;
  } else {
    b = 2;
  }
  int c = a + b;
  return c;
}

int main(int argc, char *argv[]) {
  int a = simple(argc);
  int b = loop(argc);
  int c = infinite(argc);
  int d = unreachable(argc);
  int e = diamond(argc);
  return a + b + c + d + e;
}
