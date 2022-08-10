#include <string>

int dup(std::string str) {
  std::string copy(str);
  auto newstr = new std::string(copy);
  auto sz = (copy + *newstr).size();
  if (*newstr == str) {
    sz++;
  }
  delete newstr;
  return sz;
}

int main(int argc, char **argv) { return dup(std::string(argv[0])); }
