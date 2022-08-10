#include <unistd.h>

int main() {
  int buf[(int)'a'] = {0};

  char a = 0;
  char b = 0;

  read(0, &a, 1);
  read(0, &b, 1);

  if (a != 'f') {
    return buf[0];
  } else {
    return buf[(int)a - (int)b];
  }
}
