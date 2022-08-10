#include <errno.h>
#include <stdio.h>

int changesErrno() {
  errno = -1;
  return 0;
}

int checksErrno() {
  int sc = changesErrno();
  if (errno != 0) {
    printf("Error detected!\n");
  }
  return sc;
}

int ignoresErrno() {
  int sc = changesErrno();
  printf("Hahaha! I don't care. Not going to check the errno");
  return sc;
}

int main(int argc, char *argv[]) {

  checksErrno();
  ignoresErrno();

  return 0;
}