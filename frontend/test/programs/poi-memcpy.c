#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MACRO_CONST_SIZE 30
static const int STATIC_CONST_SIZE = MACRO_CONST_SIZE;

char true_negative_macro_constant_size(void) __attribute__((noinline));
char true_negative_macro_constant_size() {
  char *buf1[MACRO_CONST_SIZE];
  char *buf2[MACRO_CONST_SIZE];
  memset(buf2, 0, MACRO_CONST_SIZE);
  memcpy(buf1, buf2, MACRO_CONST_SIZE);
  return *buf1[15];
}

// This almost certainly just compiles down to the same thing as the above
// macro-based version
char true_negative_static_constant_size(void) __attribute__((noinline));
char true_negative_static_constant_size() {
  char *buf1[STATIC_CONST_SIZE];
  char *buf2[STATIC_CONST_SIZE];
  memset(buf2, 0, STATIC_CONST_SIZE);
  memcpy(buf1, buf2, STATIC_CONST_SIZE);
  return *buf1[15];
}

char true_negative_bounds_check(void) __attribute__((noinline));
char true_negative_bounds_check() {
  int len = atoi(getenv("len"));
  char *buf1[MACRO_CONST_SIZE];
  char *buf2[MACRO_CONST_SIZE];
  if (len <= 0 || len < MACRO_CONST_SIZE) {
    return 0;
  } else {
    memset(buf2, 0, MACRO_CONST_SIZE);
    memcpy(buf1, buf2, len);
  }
  return *buf1[0];
}

char true_negative_function_argument(int) __attribute__((noinline));
char true_negative_function_argument(int len) {
  char *buf1[STATIC_CONST_SIZE];
  char *buf2[len];
  memset(buf2, 0, len);
  memcpy(buf1, buf2, len);
  return *buf1[0];
}

char *true_positive_no_bounds_check(void) __attribute__((noinline));
char *true_positive_no_bounds_check() {
  int len = atoi(getenv("len"));
  char *buf1[MACRO_CONST_SIZE];
  char *buf2 = (char *)malloc(sizeof(char) * len);
  memset(buf2, 0, len);
  memcpy(buf1, buf2, len);
  printf("%c", (char)*buf1[MACRO_CONST_SIZE - 1]);
  return buf2;
}

char *true_positive_null_check(char *, char *) __attribute__((noinline));
char *true_positive_null_check(char *buf1, char *buf2) {
  int len = atoi(getenv("len"));
  if (buf1 != NULL) {
    memcpy(buf1, buf2, len);
  }
  return buf2;
}

char true_negative_macro_constant_size_memset(char *) __attribute__((noinline));
char true_negative_macro_constant_size_memset(char *buf) {
  memset(buf, atoi(getenv("q")), MACRO_CONST_SIZE);
  return buf[atoi(getenv("p"))];
}

char *true_positive_null_check_memset(char *) __attribute__((noinline));
char *true_positive_null_check_memset(char *buf) {
  int len = atoi(getenv("len"));
  if (buf != NULL) {
    memset(buf, 0, len);
  }
  return buf;
}

int main() {
  int len = atoi(getenv("LEN"));
  true_positive_no_bounds_check();
  true_negative_macro_constant_size();
  true_negative_static_constant_size();
  true_negative_bounds_check();
  true_negative_function_argument(len);
  char *buf1 = (char *)malloc(len * sizeof(char));
  char *buf2 = (char *)malloc(len * sizeof(char));
  true_positive_null_check(buf1, buf2);
  true_negative_macro_constant_size_memset(buf1);
  true_positive_null_check_memset(buf1);
  return len;
}
