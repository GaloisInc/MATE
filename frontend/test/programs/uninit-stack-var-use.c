#include <stdlib.h>
#include <time.h>

int vuln(int arg) {
  int res;
  res = res + arg;
  return res;
}

int main() {
  srand(time(NULL));
  int r = rand();
  return vuln(r);
}
