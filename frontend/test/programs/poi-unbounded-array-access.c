#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// The values of these variables don't matter, except that the size must be
// greater than the index. Additionally, CONST_SIZE must be big enough that
// clang won't unroll loops with it as a bound at -O2.
static const int CONST_SIZE = 65536; // 2 ^ 16
static const int CONST_INDEX = 4;
static const char *ENV = "ENV";

int global = CONST_INDEX;

char true_negative_constant_index(void) __attribute__((noinline));
char true_negative_constant_index() {
  int c = atoi(getenv(ENV));
  char *buf[CONST_SIZE];
  memset(buf, c, CONST_SIZE);
  return *buf[CONST_INDEX];
}

char true_negative_bounds_check(void) __attribute__((noinline));
char true_negative_bounds_check() {
  int idx = atoi(getenv(ENV));
  char *buf[CONST_SIZE];
  memset(buf, 0, CONST_SIZE);
  if (idx >= 0 && idx < CONST_SIZE) {
    return *buf[idx];
  }
  return 0;
}

char true_positive_no_bounds_check(const char *, int) __attribute__((noinline));
char true_positive_no_bounds_check(const char *buf, int offset) {
  int i = 42 + offset;
  return buf[i];
}

// motivating example stolen from the "adams" challenge problem
char true_positive_strlen(const char *) __attribute__((noinline));
char true_positive_strlen(const char *src) {
  int i = 0;
  if (src == NULL) {
    return 0;
  }
  while (src[i] != '\x00') {
    i++;
  }
  return (char)i;
}

char true_positive_strcpy(char *, char *) __attribute__((noinline));
char true_positive_strcpy(char *dst, char *src) {
  int i = 0;
  for (i = 0; src[i] != '\0'; ++i) {
    dst[i] = src[i];
  }
  dst[i] = '\0';
  return dst[i - 1];
}

char true_positive_null_check(char *, int) __attribute__((noinline));
char true_positive_null_check(char *buf, int offset) {
  char c = 0;
  int i = 42 + offset;
  if (buf != NULL) {
    c = c ^ buf[i];
  }
  return c;
}

// TODO(lb): See test_dataflow_from_global
char false_positive_global(char *) __attribute__((noinline));
char false_positive_global(char *buf) { return buf[global]; }

char true_negative_argument_index(const char *, int) __attribute__((noinline));
char true_negative_argument_index(const char *buf, int idx) { return buf[idx]; }

typedef struct foo {
  int x;
  char y;
} foo;

char true_negative_value_struct_index(const char *, const foo)
    __attribute__((noinline));
char true_negative_value_struct_index(const char *buf, const foo x) {
  return buf[x.x];
}

char true_negative_stack_struct_index(const char *, const foo *)
    __attribute__((noinline));
char true_negative_stack_struct_index(const char *buf, const foo *x) {
  return buf[x->x];
}

// NOTE(lb): This is the same as the above, but we name it differently for
// easier debugging.
char true_negative_heap_struct_index(const char *, const foo *)
    __attribute__((noinline));
char true_negative_heap_struct_index(const char *buf, const foo *x) {
  return buf[x->x];
}

// TODO(lb): Consider a function "whitelist" for inter-procedural dataflow?
char false_negative_atoi(const char *) __attribute__((noinline));
char false_negative_atoi(const char *buf) {
  int len = atoi(getenv(ENV));
  return buf[len];
}

char false_negative_compare_to_global(const char *) __attribute__((noinline));
char false_negative_compare_to_global(const char *buf) {
  char c = 0;
  for (int i = 0; i < 4 * global; i++) {
    c = c ^ buf[i];
  }
  return c;
}

int main() {
  global++;

  int env = atoi(getenv(ENV));
  int len = env;
  char c = (char)env;
  char *buf1 = (char *)malloc(len * sizeof(char));
  char *buf2 = (char *)malloc(len * sizeof(char));
  memset(buf1, c, len);
  memset(buf2, c, len);

  char c0 = true_negative_constant_index();
  char c1 = true_negative_bounds_check();
  char c2 = true_positive_no_bounds_check(buf1, 42);
  char c3 = true_positive_strlen(buf1);
  char c4 = true_positive_strcpy(buf1, buf2);
  char c5 = true_positive_null_check(buf1, 42);
  char c6 = false_positive_global(buf1);
  char c7 = true_negative_argument_index(buf1, CONST_INDEX);

  foo w;
  w.x = env;
  w.y = (char)env;

  char c8 = true_negative_value_struct_index(buf1, w);
  char c9 = true_negative_stack_struct_index(buf1, &w);

  foo *z = (foo *)malloc(sizeof(foo));
  z->x = env;
  z->y = (char)env;
  char c10 = true_negative_heap_struct_index(buf1, z);
  free(z);

  char c11 = false_negative_atoi(buf1);

  char c12 = false_negative_compare_to_global(buf1);

  global++;
  return global ^ (int)(c0 ^ c1 ^ c2 ^ c3 ^ c4 ^ c5 ^ c6 ^ c7 ^ c8 ^ c9 ^ c10 ^
                        c11 ^ c12);
}
