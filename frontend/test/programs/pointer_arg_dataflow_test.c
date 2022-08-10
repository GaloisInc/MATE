#include <stdio.h>
#include <stdlib.h>

int globalVar = 3;

void modifies_memory(int *x, int y, int *z) { x[0] += y * z[0]; }

int does_not_modify_memory(int *x, int y, int *z) { return x[0] + y * z[0]; }

int test_array_arg(int *array) { return array[0] * array[1]; }

int test_ptr_aliasing(int *x) { return x[0] * x[0]; }

int sanity_check() { return globalVar; }

int main() {
  int *heapPtr, *stackPtr;
  int stackVal;
  stackVal = 1;
  heapPtr = (int *)malloc(sizeof(int));
  heapPtr[0] = 3;
  stackPtr = &stackVal;
  // this call does not modify any memory
  does_not_modify_memory(heapPtr, 0, stackPtr);
  // this call modifies memory pointed to by heapPtr
  modifies_memory(heapPtr, 0, stackPtr);
  // this call tests for an array used as a pointer, and does not modify memory
  int arrayNotAPointer[3];
  test_array_arg(arrayNotAPointer);
  // tests some aliasing -- this test validates that we follow on
  // LoadMemory edges if they are available, in which case we do not also
  // follow PointsTo edges
  int *alsoHeapPtr;
  alsoHeapPtr = heapPtr;
  test_ptr_aliasing(alsoHeapPtr);
  // this call does very little, for sanity check in test
  sanity_check();
  return 0;
}
