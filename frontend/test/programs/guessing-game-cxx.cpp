#include <cstdlib>
#include <iostream>

using namespace std;

int main() {
  int hidden_answer = rand() % 10 + 1;

  int guess = 0;
  cout << "Guess a number 1-10" << endl;
  cin >> guess;

  if (guess == hidden_answer) {
    cout << "You win! Number was " << hidden_answer << '.' << endl;
  } else {
    cout << "You lose!" << endl;
  }
  return 0;
}
