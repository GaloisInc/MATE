#include <stdlib.h>
#include <string.h>

// TODO(lb): This breaks everything!
// #define LARGE_CONST_SIZE 4294967295 // 2^32 - 1

#define LARGE_CONST_SIZE 128
#define SMALL_CONST_SIZE 8

int small_const_size_global[SMALL_CONST_SIZE];
int large_const_size_global[LARGE_CONST_SIZE];
int *dynamic_size_global;

void set(int *, int) __attribute__((noinline));
void set(int *buf, int sz) {
  memset(buf, rand(), sz);
  buf[1] = 5;
}

int main() {
  int dyn = atoi(getenv("DYNAMIC_DATA"));

  dynamic_size_global = (int *)malloc(sizeof(int) * dyn);

  int small_const_size_stack[SMALL_CONST_SIZE];
  int large_const_size_stack[LARGE_CONST_SIZE];
  int dynamic_size_stack[dyn];

  int *small_const_size_heap = (int *)malloc(sizeof(int) * SMALL_CONST_SIZE);
  int *large_const_size_heap = (int *)malloc(sizeof(int) * LARGE_CONST_SIZE);
  int *dynamic_size_heap = (int *)malloc(sizeof(int) * dyn);

  set(small_const_size_global, SMALL_CONST_SIZE);
  set(large_const_size_global, LARGE_CONST_SIZE);
  set(dynamic_size_global, dyn);

  set(small_const_size_stack, SMALL_CONST_SIZE);
  set(large_const_size_stack, LARGE_CONST_SIZE);
  set(dynamic_size_stack, dyn);

  set(small_const_size_heap, SMALL_CONST_SIZE);
  set(large_const_size_heap, LARGE_CONST_SIZE);
  set(dynamic_size_heap, dyn);

  return small_const_size_global[0] + large_const_size_global[0] +
         dynamic_size_global[0] + small_const_size_stack[0] +
         large_const_size_stack[0] + dynamic_size_stack[0] +
         small_const_size_heap[0] + large_const_size_heap[0] +
         dynamic_size_heap[0];
}
