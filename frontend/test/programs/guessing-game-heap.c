#include <stdio.h>
#include <stdlib.h>

struct global {
  int val;
} global_t;

struct global g = {2};

int main() {
  int *hidden_answer = (int *)malloc(sizeof(int));
  *hidden_answer = rand() % 10 + 1;

  printf("Guess a number 1-10: ");
  int guess;
  int no = scanf("%d", &guess);
  if (no != 1) {
    return 1;
  }

  printf("%d", g.val);

  int *fake = (int *)malloc(sizeof(int));
  *fake = 42;

  int *to_output;
  if (guess == *hidden_answer) {
    to_output = hidden_answer;
  } else {
    to_output = fake;
  }
  printf("%d\n", *to_output);

  free(hidden_answer);
  free(fake);
  return 0;
}
