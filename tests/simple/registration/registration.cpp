// * registration.cpp

// ** Imports and globals

#include <cstddef>
#include <functional>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

using namespace std;

size_t last_uid = 0;

// ** Types

struct User {
  size_t uid;
  string name;
  char pass;

  User(size_t uid, string name, const char pass)
      : uid(uid), name(name), pass(pass) {}

};

const User nobody{
    0,
    "nobody",
    'n',
};

struct State {
  User current_user;
  vector<User> users;
};

// ** Functionality

// Theoretically, this would be a one-way function
unsigned sanitize(unsigned x) { return (100 * x) >> 2; }

void prompt(const string &p, string &response) {
  cout << p << endl;
  getline(cin, response);
}

// Find a user in a vector
User *findUser(string needle, vector<User> haystack) {
  for (const User &user : haystack) {
    if (user.name == needle) {
      return new User(user); // copy
    }
  }
  return nullptr;
}

// Create a new user
void registerUser(vector<User> &users) {
  string username = "default username";
  prompt("Enter a username", username);
  string password = "default password";
  prompt("Enter a password (one character)", password);
  last_uid++;
  users.emplace_back(last_uid, username, password.at(0));
}

// View your UID and a hash of your password
void viewUser(const User &current) {
  cout << "UID:" << current.uid << endl;
  cout << "Pass:" << sanitize((int)current.pass) << endl;
}

User login(const User &current_user, const vector<User> &users) {
  string username = "default username";
  prompt("Enter your username:", username);
  auto user0 = findUser(username, users);
  if (user0 == nullptr) {
    cout << "No such user" << endl;
    return current_user;
  }
  auto user = *user0;
  delete user0;

  string password = "default password";
  prompt("Enter your password (one character):", password);
  if (user.pass == password.at(0)) { // TODO: check for 0 length
    return user;
  }
  cout << "Wrong password" << endl;
  return current_user;
}

User switchUser(const User &current_user, const vector<User> &users) {
  string requested_username = "default username";
  prompt("Switch to which user?", requested_username);
  for (size_t i = 0; i < users.size(); i++) {
    if (users[i].name == requested_username) {
      return users[i];
    }
  }
  cout << "That user was not found" << endl;
  return current_user;
}

// ** main

void dispatch(State &st, const string &choice) {
  switch (choice.at(0)) {
  case 'q':
    exit(0);
  case 'r':
    registerUser(st.users);
    break;
  case 'l':
    st.current_user = login(st.current_user, st.users);
    break;
  case 's':
    st.current_user = switchUser(st.current_user, st.users);
    break;
  case 'v':
    viewUser(st.current_user);
    break;
  }
}

void getInput(string &choice) {
  cout << endl;
  cout << "What would you like to do?" << endl;
  cout << "(q) quit" << endl;
  cout << "(r) register" << endl;
  cout << "(l) login" << endl;
  cout << "(v) view" << endl;
  getline(cin, choice);
}

int main() {
  vector<User> users;
  State st = State{nobody, users};
  string choice = "x";
  while (choice.compare("q")) {
    cout << endl;
    cout << "Current user: " << st.current_user.name << endl;
    getInput(choice);
    dispatch(st, choice);
  }
  cout << "Thanks, bye!" << endl;
}
