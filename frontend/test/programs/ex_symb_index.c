#include <stdio.h>
#include <stdlib.h>

int oob(int index) {
  // This function has an out of bounds index read in the SECRET variable
  // printf("Passed index: %d\n", index);
  char SECRET[25];
  return (int)(SECRET[index]);
}

int main(int argc, char **argv) {
  if (argc != 2) {
    printf("Usage: %s <number>", argv[0]);
    return -1;
  }

  int o = atoi(argv[1]);
  // printf("Converted index: %d\n", o);

  // A 0 means error, so just don't let user enter 0
  if (o != 0) {
    return oob(o);
  }
  return -1;
}
