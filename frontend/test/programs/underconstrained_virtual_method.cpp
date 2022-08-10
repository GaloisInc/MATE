

class Abstract {
public:
  virtual int a() = 0;
  virtual int b() = 0;
  virtual const char *str() = 0;
};

class Value : public Abstract {
private:
  int _a, _b;
  char _str[10];

public:
  Value() : _a(1), _b(2){};
  ~Value() = default;
  virtual int a() { return _a; };
  virtual int b() { return _b; };
  virtual char *str() { return _str; };
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