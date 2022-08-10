#include <iostream>
#include <optional>
#include <stdexcept>
#include <vector>

std::vector<std::optional<int>> cache = {0, 1, 1};

int get_nth(int n) {
  // Throws invalid_argument
  if (n < 0) {
    throw std::invalid_argument("n must be positive");
  }
  // Throws out_of_range _OR_ bad_optional_access
  if (!cache.at(n).has_value()) {
    cache[n] = cache[n - 1].value() + cache[n - 2].value();
  }
  // Should always be fine
  return cache[n].value();
}

int fib(int n) {
  while (true) {
    try {
      return get_nth(n);
    } catch (const std::invalid_argument &e) {
      // We passed a negative number
      return 0;
    } catch (const std::out_of_range &e) {
      // We didn't have room in the cache to calculate this result
      for (int i = 0; i < 10; i++) {
        cache.push_back(std::nullopt);
      }
    } catch (const std::bad_optional_access &e) {
      // We didn't have this result in the cache yet
      fib(n - 2);
      fib(n - 1);
    }
  }
}

int main(int argc, char *argv[]) {
  if (argc != 2) {
    std::cout << "Need one integer as an argument" << argc << '\n';
    return -1;
  }

  std::cout << "fib(" << argv[1] << ") == " << fib(atoi(argv[1])) << "\n";
  return 0;
}
