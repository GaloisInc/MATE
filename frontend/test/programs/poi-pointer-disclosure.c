/* Test program for uninitialized stack memory usage POI */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/timex.h>
#include <unistd.h>

typedef struct {
  char buf[10];
} bufstruct;
typedef struct {
  void *ptr;
} ptrstruct;
typedef struct {
  char buf[10];
  void *ptr;
} bufptrstruct;
typedef struct {
  char buf1[10];
  char buf2[10];
} bufbufstruct;

void true_positive_buf_struct() {
  void *p = malloc(10);

  bufstruct s;
  sprintf(s.buf, "%p\n", p);

  printf("%s", s.buf);

  free(p);
}

void true_positive_ptr_struct() {
  void *p = malloc(10);

  ptrstruct s;
  s.ptr = p;

  printf("%p\n", s.ptr);

  free(p);
}

void true_positive_bufptr_struct() {
  void *p = malloc(10);

  bufptrstruct s;
  s.ptr = p;

  printf("%p\n", s.ptr);

  free(p);
}

void true_positive_bufbuf_struct() {
  void *p = malloc(10);

  bufbufstruct s;
  sprintf(s.buf2, "%p\n", p);

  printf("%s", s.buf2);

  free(p);
}

void false_positive_bufptr_struct() {
  void *p = malloc(10);

  bufptrstruct s;
  s.buf[0] = 0;
  s.ptr = p;

  printf("%s\n", s.buf);

  free(p);
}

void false_positive_bufbuf_struct() {
  void *p = malloc(10);

  bufbufstruct s;
  s.buf1[0] = 0;
  sprintf(s.buf2, "%p\n", p);

  printf("%s", s.buf1);

  free(p);
}

int main(int argc, char **argv) {
  true_positive_buf_struct();
  true_positive_ptr_struct();
  true_positive_bufptr_struct();
  true_positive_bufbuf_struct();
  false_positive_bufptr_struct();
  false_positive_bufbuf_struct();
}
