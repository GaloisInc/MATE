#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void try_print_from_file(FILE *f) {
  char data[64];
  char *result = fgets(data, sizeof(data), f);
  if (result == NULL) {
    fclose(f);
    return;
  }
  printf("%s\n", data);
  fclose(f);
}

int main() {
  // User input
  char path[64];
  char *result = fgets(path, sizeof(path), stdin);
  if (result == NULL) {
    return EXIT_FAILURE;
  }

  // True positive: User input controls path
  FILE *f = fopen(path, "r");
  if (f == NULL) {
    return EXIT_FAILURE;
  }
  try_print_from_file(f);

  // False positive: User input is fully statically known at this point
  if (strcmp(path, "/dev/null") == 0) {
    f = fopen(path, "r");
    if (f == NULL) {
      return EXIT_FAILURE;
    }
    try_print_from_file(f);
  }

  // True negative
  f = fopen("/dev/null", "r");
  if (f == NULL) {
    return EXIT_FAILURE;
  }
  try_print_from_file(f);

  return 0;
}
