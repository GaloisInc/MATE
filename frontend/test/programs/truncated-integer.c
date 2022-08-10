#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Use this wrapper around `malloc` to avoid it being inlined and optimized out
// entirely.
__attribute__((noinline)) char *alloc_buffer(unsigned long alloc_size) {
  return malloc(alloc_size);
}

void print_truncated_alloc_size(int alloc_size) {
  printf("alloc_size: %d\n", alloc_size);
}

int main(int argc, char **argv) {
  if (argc != 1) {
    printf("usage: ./prog < num\n");
    exit(1);
  }

  // This should be flagged as a POI since we're doing a dynamic allocation with
  // a user-controllable size and then truncating the size elsewhere.
  unsigned long alloc_size1;
  scanf("%lu", &alloc_size1);
  char *buf1 = alloc_buffer(alloc_size1);
  print_truncated_alloc_size(alloc_size1);

  // This should not be flagged as a POI since we're not truncating the
  // allocation size.
  unsigned long alloc_size2;
  scanf("%lu", &alloc_size2);
  char *buf2 = alloc_buffer(alloc_size2);

  // This should not be flagged as a POI since we're not allocating with the
  // size value.
  unsigned long alloc_size3;
  scanf("%lu", &alloc_size3);
  print_truncated_alloc_size(alloc_size3);

  // This should be flagged as a POI since we're casting to an `int` and
  // therefore truncating the size in the `printf` invocation. This is a more
  // realistic example.
  unsigned long alloc_size4;
  scanf("%lu", &alloc_size4);
  char *buf4 = alloc_buffer(alloc_size4);
  memset(buf4, 0x0, alloc_size4);
  printf("buffer: %.*s\n", (int)alloc_size4, buf4);
}
