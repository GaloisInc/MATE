#include <string.h>

void func() {
  char *s = "afsdfiuhsdofiuhsdfiqudfhngghodfiuyghdfiguhdfug";
  char *dst = malloc(8 * sizeof(char));
  strcpy(dst, s);
}

int main() {
  func();
  return 0;
}