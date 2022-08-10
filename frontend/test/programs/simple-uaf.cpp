#include <iostream>

struct List {
  explicit List(int data) : data(data), next(nullptr) {}
  List(int data, List *next) : data(data), next(next) {}
  int data;
  List *next;
};

int main(int argc, char *argv[]) {
  int a = 1, b = 2, c = 3;

  List *elem1 = new List(a);
  List *elem2 = new List(b, elem1);
  List *head = new List(c, elem2);

  delete head->next;

  List *iter = head;
  while (iter) {
    std::cout << iter->data << std::endl;
    iter = iter->next;
  }

  return 0;
}
