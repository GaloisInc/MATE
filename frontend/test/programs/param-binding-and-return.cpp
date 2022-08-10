#include <stdio.h>

// so that the call with no args & no return has something to do
int global_value = 0;
int another_global_value = 3;

void no_args_no_return() {
  if (global_value > 4) {
    global_value = another_global_value;
  }
}

int no_args_int_return() {
  if (global_value > 4) {
    return global_value;
  }
  return another_global_value;
}

void one_arg_no_return(int x) { global_value += x; }

int one_arg_int_return(int x) {
  global_value += x;
  return global_value;
}

void one_pointer_arg_no_return(bool *y) {
  if (y[0]) {
    global_value += 42;
  }
}

void two_args_no_return(int x, bool *y) {
  if (y[0]) {
    global_value += x;
  }
}

int two_args_int_return(int x, bool *y) {
  if (y[0]) {
    global_value += x;
  }
  return global_value;
}

int main() {
  bool *truth_pntr = new bool[1];
  truth_pntr[0] = true;
  no_args_int_return();
  no_args_no_return();
  one_arg_no_return(4);
  one_arg_int_return(4);
  one_pointer_arg_no_return(truth_pntr);
  two_args_no_return(4, truth_pntr);
  two_args_int_return(4, truth_pntr);
  // second call to the same function
  two_args_int_return(5, truth_pntr);
  return 0;
}
