/* This is a regression case for MATE#1137.
 * Ref: https://gitlab-ext.galois.com/mate/MATE/-/issues/1137
 */

#include <stdio.h>
#include <stdlib.h>

struct foo {
  int n;
  int things[0];
};

int main(int argc, char const *argv[]) {
  int n = getchar();
  if (n <= 0) {
    return 1;
  }

  struct foo *flexible = malloc(sizeof(struct foo) + (n * sizeof(int)));

  flexible->n = n;
  for (int i = 0; i < n; ++i) {
    flexible->things[i] = i;
  }

  return flexible->things[n - 1];
}
