/* Taken from http://phrack.org/issues/63/14.html, tweaked slightly to take
 * user input instead of argv.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

int func(int len, char *stuff) {
  char x[len];

  printf("sizeof(x): %zu\n", sizeof(x));
  strncpy(x, stuff, 4);
  return 58;
}

int main(int argc, char **argv) {
  char input[64];
  scanf("%c", input);
  return func(atoi(input), argv[1]);
}
