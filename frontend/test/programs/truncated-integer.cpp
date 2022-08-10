#include <iostream>
#include <stdio.h>

__attribute__((noinline)) char *alloc_buffer(unsigned long alloc_size) {
  return new char[alloc_size];
}

void print_truncated_alloc_size(int alloc_size) {
  std::cout << alloc_size << std::endl;
}

int main(int argc, char **argv) {
  unsigned long alloc_size;
  scanf("%lu", &alloc_size);
  char *buf = alloc_buffer(alloc_size);
  print_truncated_alloc_size(alloc_size);
  delete[] buf;
}
