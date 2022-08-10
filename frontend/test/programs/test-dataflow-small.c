#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// The values of these variables don't matter, except that the size must be
// greater than the index. Additionally, CONST_SIZE must be big enough that
// clang won't unroll loops with it as a bound at -O2.
static const int CONST_INDEX = 4;
static const char *ENV = "ENV";

int global = CONST_INDEX;

typedef struct foo {
  int x;
  char y;
} foo;

char true_negative_value_struct_index(const char *, const foo)
    __attribute__((noinline));
char true_negative_value_struct_index(const char *buf, const foo x) {
  return buf[x.x];
}

char stack(const char *, const foo *) __attribute__((noinline));
char stack(const char *buf, const foo *x) { return buf[x->x]; }

// NOTE(lb): This is the same as the above, but we name it differently for
// easier debugging.
char heap(const char *, const foo *) __attribute__((noinline));
char heap(const char *buf, const foo *x) { return buf[x->x]; }

int main() {
  global++;

  int env = atoi(getenv(ENV));
  int len = env;
  char c = (char)env;
  char *buf1 = (char *)malloc(len * sizeof(char));
  char *buf2 = (char *)malloc(len * sizeof(char));
  memset(buf1, c, len);
  memset(buf2, c, len);

  foo w;
  w.x = env;
  w.y = (char)env;

  char c8 = true_negative_value_struct_index(buf1, w);
  char c9 = stack(buf1, &w);

  foo *z = (foo *)malloc(sizeof(foo));
  z->x = env;
  z->y = (char)env;
  char c10 = heap(buf1, z);
  free(z);

  global++;
  return global ^ (int)(c8 ^ c9 ^ c10);
}
