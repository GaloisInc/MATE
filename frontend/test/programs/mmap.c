#include <stdio.h>
#include <sys/mman.h>

#define SIZE 8

int main(int argc, char **argv) {
  char *buf = mmap(0,                // starting address hint
                   SIZE,             // size = 8 bytes
                   PROT_READ         // can be read
                       | PROT_WRITE, // can be written
                   MAP_ANONYMOUS,    // not file-backed, zero-initialized
                   0, 0);
  for (int i = 0; i < SIZE; i++) {
    putchar(buf[i]);
  }
  return munmap(buf, SIZE);
}
