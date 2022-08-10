class Root {
  int _bar;

public:
  virtual int bar() { return _bar; };
};

class Abstract1 {
  int _b;

public:
  virtual int b() { return _b; };
  virtual const char *str() = 0;
};

class Abstract2 : public Root {
  int _a;
  char _c;

public:
  int a() { return _a; };
  virtual char c() { return _c; };
};

class Value : public Abstract1, public Abstract2 {
private:
  char _str[10];

public:
  Value() = default;
  ~Value() = default;
  virtual char *str() { return _str; };
  virtual char c() { return _str[0]; };
};

int func(Value *value) {
  if (value->a() == value->b())
    if (value->bar() == (int)(value->str()[0]))
      return 2;
    else
      return 1;
  else
    return 0;
}

int main(int argc, char const *argv[]) {
  Value value;
  return func(&value);
}