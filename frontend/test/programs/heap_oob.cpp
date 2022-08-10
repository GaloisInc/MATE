#include <cstring>
#include <new>

class A {
public:
  char buf[8];
};

class B {
public:
  char buf[8];
  void *operator new(size_t sz) {
    void *p = ::operator new(sz);
    return p;
  }
};

void func() {
  char *s = "afsdfiuhsdofiuhsdfiqudfhngghodfiuyghdfiguhdfug";
  A *a = new A();
  strcpy(a->buf, s);
}

// Using void* operator new  ( std::size_t count, std::align_val_t al );
void func2() {
  char *s = "afsdfiuhsdofiuhsdfiqudfhngghodfiuyghdfiguhdfug";
  char *dst = (char *)(::operator new(8, (std::align_val_t)0x1000));
  strcpy(dst, s);
}

// Using void* operator new  []( std::size_t count);
void func3() {
  char *s = "afsdfiuhsdofiuhsdfiqudfhngghodfiuyghdfiguhdfug";
  void *dst = ::operator new[](15);
  strcpy((char *)dst, s);
}

// Using B::operator new()
void func4() {
  char *s = "afsdfiuhsdofiuhsdfiqudfhngghodfiuyghdfiguhdfug";
  B *b = new B();
  strcpy(b->buf, s);
}

int main() {
  func();
  return 0;
}