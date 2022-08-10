#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// The values of these variables don't matter, except their relative ordering.
#define SMALL_SIZE 8
#define SMALL_INDEX 4
#define LARGE_SIZE 128
#define LARGE_INDEX 64
#define REALLY_LARGE_INDEX 256
#define ENV "ENV"

char true_negative_always_in_bounds_one_use(char *) __attribute__((noinline));
char true_negative_always_in_bounds_one_use(char *buf) {
  return buf[SMALL_INDEX];
}

char true_negative_always_in_bounds_two_use(char *) __attribute__((noinline));
char true_negative_always_in_bounds_two_use(char *buf) {
  return buf[SMALL_INDEX];
}

char true_positive_sometimes_in_bounds_one_use(char *)
    __attribute__((noinline));
char true_positive_sometimes_in_bounds_one_use(char *buf) {
  return buf[LARGE_INDEX];
}

char true_positive_sometimes_in_bounds_two_use(char *)
    __attribute__((noinline));
char true_positive_sometimes_in_bounds_two_use(char *buf) {
  return buf[LARGE_INDEX];
}

char true_positive_never_in_bounds_one_use(char *) __attribute__((noinline));
char true_positive_never_in_bounds_one_use(char *buf) {
  return buf[REALLY_LARGE_INDEX];
}

char true_positive_never_in_bounds_two_use(char *) __attribute__((noinline));
char true_positive_never_in_bounds_two_use(char *buf) {
  return buf[REALLY_LARGE_INDEX];
}

int main() {
  int env = atoi(getenv(ENV));
  char small_buf[SMALL_SIZE];
  char large_buf[LARGE_SIZE];
  memset(small_buf, env, SMALL_SIZE);
  memset(large_buf, env, LARGE_SIZE);

  char c0 = true_negative_always_in_bounds_one_use(small_buf);
  char c1 = true_negative_always_in_bounds_two_use(small_buf);
  c1 ^= true_negative_always_in_bounds_two_use(large_buf);

  char c2 = true_positive_sometimes_in_bounds_one_use(small_buf);
  char c3 = true_positive_sometimes_in_bounds_two_use(small_buf);
  c3 ^= true_negative_always_in_bounds_two_use(large_buf);

  char c4 = true_positive_never_in_bounds_one_use(small_buf);
  char c5 = true_positive_never_in_bounds_two_use(small_buf);
  c5 ^= true_positive_never_in_bounds_two_use(large_buf);
  return (int)(c0 ^ c1 ^ c2 ^ c3 ^ c4 ^ c5);
}
