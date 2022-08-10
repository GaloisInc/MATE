#include <array>
#include <iostream>
#include <string.h>

struct Buffer {
  Buffer() { val.fill(0); }
  std::array<char, 1024> val;
};

__attribute__((noinline)) Buffer *allocate_buffer() { return new Buffer; }

__attribute__((noinline)) char *
allocate_variable_length_buffer(unsigned long buf_size) {
  char *buf = new char[buf_size + 1024];
  memset(buf, 0x0, buf_size);
  return buf;
}

int main(int argc, char **argv) {
  Buffer *buf1 = allocate_buffer();
  for (char c : buf1->val) {
    std::cout << c;
  }
  std::cout << std::endl;
  unsigned long num1;
  scanf("%lu", &num1);
  char *buf2 = allocate_variable_length_buffer(num1);
  std::cout << buf2 << std::endl;
  delete buf1;
  delete[] buf2;
  return 0;
}
