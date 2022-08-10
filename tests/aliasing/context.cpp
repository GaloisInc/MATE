class MyObj {};

class A1 : public MyObj {};

class A2 : public MyObj {};

MyObj *id(MyObj *a) { return a; }

void fun1() {
  MyObj *a1 = new A1();
  MyObj *b1 = id(a1);
}

void fun2() {
  MyObj *a2 = new A2();
  MyObj *b2 = id(a2);
}

int main() {
  fun1();
  fun2();
}
