#include <fcntl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __cplusplus
#include <exception>
#include <functional>
#include <iostream>
#include <numeric>
#include <string>
#include <system_error>
#include <vector>
#endif

#define COINFLIP() (rand() % 2)

std::vector<int> build_list(void) {
  std::vector<int> nums;
  for (int i = 0; i < 1024; ++i) {
    if (COINFLIP()) {
      nums.push_back(COINFLIP() + COINFLIP() + COINFLIP());
    } else {
      nums.push_back(COINFLIP() + COINFLIP() + COINFLIP() + 1);
    }
  }

  return nums;
}

void invalidate_iterator_with_erasure(void) {
  auto nums = build_list();

  std::cout << nums.size() << std::endl;
  auto end = nums.end();

  for (auto i = nums.begin(); i != end; ++i) {
    if (*i % 2 == 0) {
      std::cout << "erasing" << std::endl;
      nums.erase(i);
    }
  }

  std::cout << nums.size() << std::endl;
}

void invalidate_iterator_with_insertion(void) {
  auto nums = build_list();

  std::cout << nums.size() << std::endl;
  auto end = nums.end();

  for (auto i = nums.begin(); i != end; ++i) {
    const int new_val = *i * 2;
    nums.push_back(new_val);
  }

  std::cout << nums.size() << std::endl;
}

void invalidate_iterator_with_resize(void) {
  auto nums = build_list();

  std::cout << nums.size() << std::endl;
  auto end = nums.end();

  for (auto i = nums.begin(); i != end; ++i) {
    if (*i % 2 == 0) {
      nums.resize(nums.size() + 1, 0);
    }
  }

  std::cout << nums.size() << std::endl;
}

void multiple_containers(void) {
  auto nums1 = build_list(), nums2 = build_list();

  std::cout << nums1.size() << std::endl;
  auto end = nums1.end();

  for (auto i = nums1.begin(); i != end; ++i) {
    if (*i % 2 == 0) {
      std::cout << "erasing" << std::endl;
      nums2.erase(i);
    }
  }

  std::cout << nums1.size() << std::endl;
}

void reconstruct_iterator(void) {
  auto nums = build_list();

  std::cout << nums.size() << std::endl;
  auto end = nums.end();

  while (!nums.empty()) {
    auto i = nums.begin();
    if (*i % 2 == 0) {
      std::cout << *i << std::endl;
    }
    nums.erase(i);
  }

  std::cout << nums.size() << std::endl;
}

void no_invalidation(void) {
  auto nums = build_list();

  std::cout << nums.size() << std::endl;
  auto end = nums.end();

  for (auto i = nums.begin(); i != end; ++i) {
    if (*i % 2 == 0) {
      std::cout << "Back is " << nums.back() << std::endl;
    }
  }

  std::cout << nums.size() << std::endl;
}

void no_usage(void) {
  auto nums = build_list();

  std::cout << nums.size() << std::endl;

  auto i = nums.begin();
  nums.erase(i);

  std::cout << nums.size() << std::endl;
}

void reconstruct_iterator_false_negative(void) {
  auto nums = build_list();

  std::cout << nums.size() << std::endl;
  auto end = nums.end();

  for (auto i = nums.begin(); i != end; ++i) {
    auto j = nums.begin();
    if (*i % 2 == 0) {
      std::cout << *i << std::endl;
    }
    nums.erase(i);
  }

  std::cout << nums.size() << std::endl;
}

int main(int argc, char const *argv[]) {
  // This should be flagged as a POI.
  //
  // We invalidate an iterator with a call to `erase` then dereference it.
  invalidate_iterator_with_erasure();

  // This should be flagged as a POI.
  //
  // We invalidate an iterator with a call to `push_back` then dereference it.
  invalidate_iterator_with_insertion();

  // This should be flagged as a POI.
  //
  // We invalidate an iterator with a call to `resize` then dereference it.
  invalidate_iterator_with_resize();

  // This should not be flagged as a POI.
  //
  // We call the invalidating method on a different container to the one that we
  // retrieve the iterator from.
  multiple_containers();

  // This should not be flagged as a POI.
  //
  // We reconstruct the iterator between invalidating it and dereferencing it.
  reconstruct_iterator();

  // This should not be flagged as a POI.
  //
  // We use a method on the container that does not invalidate iterators.
  no_invalidation();

  // This should not be flagged as a POI.
  //
  // We use a method on the container that invalidates iterators, but we don't
  // use any iterators after the call.
  no_usage();

  // This isn't expected to be flagged as a POI, but ideally it should.
  //
  // We construct a completely separate iterator between invalidation and usage
  // but our query is unable to differentiate between this scenario and the
  // `reconstruct_iterator` one and filters it out.
  reconstruct_iterator_false_negative();

  return 0;
}
