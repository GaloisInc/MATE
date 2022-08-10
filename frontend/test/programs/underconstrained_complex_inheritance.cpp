class Abstract1 {
  int _b;

public:
  virtual int b() { return _b; };
  virtual const char *str() = 0;
};

class Abstract2 {
  int _a;
  char _c;

public:
  virtual int a() { return _a; };
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
    return 1;
  else
    return 0;
}

int main(int argc, char const *argv[]) {
  Value value;
  return func(&value);
}