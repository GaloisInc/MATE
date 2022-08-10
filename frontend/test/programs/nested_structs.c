#include <stdio.h>
#include <stdlib.h>

// This number is chosen because it's the largest 1 digit integer
#define BUFFER_SIZE 9

struct nested {
  char buf[20];
  char large[100];
};

int overflow_field(int index) {
  struct authentication {
    char buffer[BUFFER_SIZE];
    int authenticated;
    struct nested nest;
  } auth;
  // This function has an out of bounds index read in the auth.buffer
  return (int)auth.buffer[index];
}

int main(int argc, char **argv) {
  if (argc != 2) {
    printf("Usage: %s <number>", argv[0]);
    return 1;
  }

  return overflow_field(atoi(argv[1]));
}
