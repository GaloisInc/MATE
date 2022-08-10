#include <stdio.h>
#include <stdlib.h>

char *my_calloc(size_t count, size_t size) { return malloc(count * size); }

typedef struct {
  int *ptr;
} int_struct;

typedef struct {
  double *ptr;
} double_struct;

void print_int(int_struct *s) { printf("%d\n", *s->ptr); }

void print_double(double_struct *s) { printf("%f\n", *s->ptr); }

void use_int() {
  int x = 0;
  int_struct *s = (int_struct *)my_calloc(1, sizeof(int_struct));
  s->ptr = &x;
  print_int(s);
}

void use_double() {
  double x = 0;
  double_struct *s = (double_struct *)my_calloc(1, sizeof(double_struct));
  s->ptr = &x;
  print_double(s);
}

int main(int argc, char *argv[]) {
  use_int();
  use_double();
}
