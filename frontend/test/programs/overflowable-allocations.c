#include <stdio.h>
#include <stdlib.h>
#include <string.h>

__attribute__((noinline)) char *
allocate_buffer_with_header(unsigned long header_size) {
  char *buf = malloc(header_size + 1024);
  memset(buf, 0x1, header_size);
  return buf;
}

__attribute__((noinline)) char *allocate_buffer(unsigned long buf_size) {
  char *buf = malloc(buf_size);
  memset(buf, 0x1, buf_size);
  return buf;
}

int main(int argc, char **argv) {
  if (argc != 1) {
    printf("usage: ./prog < num\n");
    exit(1);
  }
  // This should be flagged as a POI since the allocation helper performs an
  // addition before being passed to `malloc`
  unsigned long num1;
  scanf("%lu", &num1);
  char *buf1 = allocate_buffer_with_header(num1);
  printf("header: %.*s", num1, buf1);
  // This should not be flagged as a POI since there's no arithmetic operation
  // between the input and `malloc`
  unsigned long num2;
  scanf("%lu", &num2);
  char *buf2 = allocate_buffer(num2);
  printf("buffer: %.*s", num2, buf2);
  // This should be flagged as a POI since the input is subtracted from before
  // being passed to the allocation helper
  unsigned long num3;
  scanf("%lu", &num3);
  num3--;
  char *buf3 = allocate_buffer(num3);
  printf("buffer: %.*s", num3, buf3);
  return 0;
}
