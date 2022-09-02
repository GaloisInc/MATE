/*
MIT License

Copyright (c) 2019 yuawn

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>

void init() {
  setvbuf(stdout, 0, 2, 0);
  setvbuf(stdin, 0, 2, 0);
  setvbuf(stderr, 0, 2, 0);
}

int read_int() {
  char buf[0x10];
  __read_chk(0, buf, 0xf, 0x10);
  return atoi(buf);
}

void welcome_func() { puts("Hello ~~~"); }

void bye_func() { puts("Bye ~~~"); }

void menu() {
  puts("1. add a box");
  puts("2. exit");
  puts(">");
}

struct MessageBox {
  void (*welcome)();
  void (*bye)();
};

void backdoor() { system("sh"); }

int main() {

  init();

  struct MessageBox *msgbox =
      (struct MessageBox *)malloc(sizeof(struct MessageBox));

  msgbox->welcome = welcome_func;
  msgbox->bye = bye_func;

  msgbox->welcome();
  free(msgbox);

  int n = 3, size;
  char *msg;

  while (n--) {
    printf("Size of your message: ");
    size = read_int();

    msg = (char *)malloc(size);

    printf("Message: ");
    read(0, msg, size);

    printf("Saved message: %s\n", msg);

    free(msg);
  }

  msgbox->bye();

  return 0;
}
