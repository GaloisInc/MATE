#include <stdio.h>

int foo() { return 2; }

int main() {
  int x = foo();
  int y = foo();

  int a = 0;
  int b = 1;
  int c = 2;
  int d = 3;
  int *arr[] = {&a, &b, &c, &d};

  int *px = arr[x];
  int *py = arr[y];

  printf("%d %d", *px, *py);
}
