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
#define NODE_COUNT 3

class ListNode {
public:
  void *data;
  ListNode *next;

  ListNode() { std::cout << "foo\n"; }

  void printList() {
    ListNode *head = this;
    std::cout << "List:\n";
    while (head) {
      head->printSelf();
      head = head->next;
    }
  }

  void printSelf() {
    std::cout << "node(" << this << ") = " << this->next << ", "
              << *((int *)this->data) << '\n';
  }
};

unsigned char
    global_buf[sizeof(ListNode) * NODE_COUNT + sizeof(int) * NODE_COUNT];
int array[] = {1, 2, 3};

int main(int argc, char const *argv[]) {

  // Buffer on stack
  unsigned char stack_buf[sizeof(int) * 3];

  int *a = new (stack_buf) int(25);
  int *b = new (stack_buf + sizeof(int)) int(1000);
  int *c = new (stack_buf + sizeof(int) * 2) int(1);

  std::cout << "a = " << *a << '\n';
  std::cout << "b = " << *b << '\n';
  std::cout << "c = " << *c << '\n';

  // Buffer on the heap
  unsigned char *buf_heap = new unsigned char[sizeof(ListNode) * 3];

  ListNode *head = new (buf_heap) ListNode();
  ListNode *next = new (buf_heap + sizeof(ListNode)) ListNode();
  ListNode *tail = new (buf_heap + 2 * sizeof(ListNode)) ListNode();

  head->data = a;
  head->next = next;
  next->data = b;
  next->next = tail;
  tail->data = c;
  tail->next = NULL;

  // Buffer in BSS (uninitialized data)
  int offset = 0;
  ListNode *head2 = new (global_buf) ListNode();
  offset += sizeof(ListNode);
  head2->data = new (global_buf + offset) int(10);
  offset += sizeof(int);

  ListNode *next2 = new (global_buf + offset) ListNode();
  offset += sizeof(ListNode);
  next2->data = new (global_buf + offset) int(20);
  offset += sizeof(int);

  ListNode *tail2 = new (global_buf + offset) ListNode();
  offset += sizeof(ListNode);
  tail2->data = new (global_buf + offset) int(30);

  tail->next = head2;
  head2->next = next2;
  next2->next = tail2;
  tail2->next = NULL;

  head->printList();

  // Buffer in Data Section (initialized data)
  int *d = new (array) int(300);
  int *e = new (array + 1) int(400);
  int *f = new (array + 2) int(500);

  std::cout << "d = " << *d << '\n';
  std::cout << "e = " << *e << '\n';
  std::cout << "f = " << *f << '\n';
}
