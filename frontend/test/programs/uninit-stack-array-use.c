#include <stdlib.h>
#include <time.h>

int vuln(int arg) {
  int res[10];
  res[3] = arg * 2;
  res[5] = arg + res[3];
  return res[0] + res[5];
}

int main() {
  srand(time(NULL));
  int r = rand();
  return vuln(r);
}
