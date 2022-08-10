class Abstract1 {
public:
  int _b;
  char _d;
};

class Abstract2 {
public:
  int _a;
  char _c;
};

class Value : public Abstract1, public Abstract2 {
public:
  char _str[10];
};

int func(Value *value) {
  if (value->_a == value->_b)
    return 1;
  else
    return 0;
}

int main(int argc, char const *argv[]) {
  Value value;
  return func(&value);
}