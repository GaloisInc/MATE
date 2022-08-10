#include <stdio.h>
#include <stdlib.h>

// This number is chosen because it's the largest 1 digit integer
#define BUFFER_SIZE 9

struct third_nest {
  char buf[5];
  char large[18];
};

struct second_nest {
  double hello;
  struct third_nest third;
  int why;
};

struct first_nest {
  char buf[20];
  struct second_nest second;
};

int overflow_field(int index) {
  struct authentication {
    char buffer[BUFFER_SIZE];
    int authenticated;
    struct first_nest nest;
    double end;
  } auth;
  // This function has an out of bounds index read in the auth.buffer
  auth.buffer[4] = 10;
  return (int)auth.buffer[index];
}

int main(int argc, char **argv) {
  if (argc != 2) {
    printf("Usage: %s <number>", argv[0]);
    return 1;
  }

  return overflow_field(atoi(argv[1]));
}
