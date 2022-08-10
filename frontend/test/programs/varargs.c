// https://www.gnu.org/software/libc/manual/html_node/Variadic-Example.html#Variadic-Example
#include <stdarg.h>
#include <stdio.h>

int add_em_up(int count, ...) {
  va_list ap;
  int i, sum;

  va_start(ap, count); /* Initialize the argument list. */

  sum = 0;
  for (i = 0; i < count; i++)
    sum += va_arg(ap, int); /* Get the next argument value. */

  va_end(ap); /* Clean up. */
  return sum;
}

int main(void) {
  printf("%d\n", add_em_up(3, 5, 5, 6));
  printf("%d\n", add_em_up(10, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10));

  typeof(add_em_up) *add_em_up_ptr = add_em_up;
  printf("%d\n", add_em_up_ptr(4, 1, 2, 3, 4));
  return 0;
}
