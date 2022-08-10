#include <stdio.h>
#include <stdlib.h>

int main() {
  int hidden_answer = rand() % 10 + 1;

  printf("Guess a number 1-10: ");
  int guess;
  int no = scanf("%d", &guess);
  if (no != 1) {
    return 1;
  }

  if (guess == hidden_answer) {
    printf("You win! Number was %d.\n", hidden_answer);
  } else {
    printf("You lose!\n");
  }
  return 0;
}
