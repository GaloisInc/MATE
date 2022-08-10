#include <stdio.h>
#include <stdlib.h>

int bar(int c) {
  if (c > 50) {
    printf("secret is greater than 50\n");
    return -3;
  }
  printf("Hooray! Secret is less than or equal to 50\n");
  return c;
}

int foo(int b) {
  if (b < 0) {
    return -1;
  } else if (b < 5) {
    printf("num is less than 5\n");
    return -2;
  } else {
    printf("num is greater than or equal to 5\n");
    int t = bar(b * 8);
    return t;
  }
}

int main(int argc, char **argv) {
  if (argc != 2) {
    printf("usage: ./prog num\n");
    exit(1);
  }

  int num = atoi(argv[1]);
  return (foo(num));
}
