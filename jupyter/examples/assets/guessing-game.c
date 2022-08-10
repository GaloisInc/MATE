#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct secret {
  int number;
} secret_t;

secret_t hidden;

void get_guess(int *guess);
void print_guesses(int *guesses, int i);

int main() {
  hidden.number = rand() % 10 + 1;

  int *guesses = calloc(9, sizeof(int));

  for (int i = 0; i < 9; i++) {
    get_guess(&guesses[i]);
 
    if (guesses[i] == hidden.number) {
      printf("You win! the secret was %d\n", hidden.number);
      free(guesses);
      return 0;
    } else {
      printf("Wrong answer!\n");
      print_guesses(guesses, i);
    }
  }

  printf("You're out of guesses, sorry.\n");

  free(guesses);
  return -1;
}

int read_num(int *num) {
  int no = scanf("%d", num);
  if (no != 1) {
    return 1;
  }
  if ((*num < 1) || (*num > 10)) {
    return 2;
  }
  return 0;
}

void get_guess(int *guess) {
  printf("Guess a number 1-10: ");
  while (true) {
    if (read_num(guess) == 0) {
      return;
    } else {
      printf("Invalid entry. Try again.\n");
    }
  }
}

void print_guesses(int *guesses, int i) {
  printf("Your guesses so far:");
  for (int j = 0; j <= i; j++) {
    printf(" %d", guesses[j]);
  }
  printf("\n");
}
