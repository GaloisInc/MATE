#include <stdlib.h>

int global = 42;

int reads_global(int) __attribute__((noinline));
int reads_global(int x) { return x + global; }

char reads_global_cast(char) __attribute__((noinline));
char reads_global_cast(char x) { return x + (char)global; }

int writes_global(int) __attribute__((noinline));
int writes_global(int x) {
  global = global + x;
  return global;
}

int main() {
  int env = atoi(getenv("ENV"));
  global = env;
  return reads_global(env) ^ ((int)reads_global_cast((char)env)) ^
         writes_global(env);
}
