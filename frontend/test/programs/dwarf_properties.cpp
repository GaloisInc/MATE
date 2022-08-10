#include <fcntl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __cplusplus
#include <exception>
#include <functional>
#include <iostream>
#include <numeric>
#include <string>
#include <system_error>
#include <vector>
#endif

#define COINFLIP() (rand() % 2)

using namespace std;

class Animal {
public:
  void act() {
    if (COINFLIP()) {
      cout << "woof" << endl;
    } else {
      cout << "meow" << endl;
    }
  }
};

class Dolphin : public Animal {
public:
  void act() { cout << "chitter" << endl; }
};

enum Month { Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec };

union Color {
  unsigned int red;
  unsigned int green;
  unsigned int blue;
};

struct ListNode {
  int val;
  struct ListNode *next;
};

void printMonth(enum Month m) { printf("%d", m); }

void setMonths(int len, int a[]) {
  int i;
  for (i = Jan; i <= len; i++) {
    a[i] = i;
  }
}

int main(int argc, char const *argv[]) {
  Animal a;
  a.act();

  Dolphin d;
  d.act();

  enum Month jan = Jan;
  printMonth(jan);

  union Color color;
  color.red = 0;
  color.green = 1;
  color.blue = 2;

  struct ListNode head;
  head.val = 100;
  head.next = NULL;

  int len = 12;
  int months[len];

  void (*fp)(int, int[]) = &setMonths;
  fp(len, months);

  return 0;
}
