#include <vector>

int func(std::vector<int> &vec) {
  int res = 0;
  int i;
  for (i = 0; i < 10; i++)
    vec.push_back(i);
  for (i = 0; i < 3; i++)
    vec.pop_back();
  for (int val : vec)
    res += val;
  if (vec.size() == 9)
    return res;
  else
    return 0;
}

int main(int argc, char **argv) {
  std::vector<int> vec;
  return func(vec);
}