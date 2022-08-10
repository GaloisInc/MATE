#define _GNU_SOURCE

#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "db.h"
#include "execute.h"
#include "kvlist.h"
#include "log.h"
#include "plan.h"
#include "query_parser.h"
#include "session.h"

#define COMMAND_BUF_SIZE 120
#define MESSAGE_BUF_SIZE 120

bool streq(char* left, char* right);

void list_commands(FILE* out);
void list_users(FILE* out, database* db);
kvlist* login(FILE* out, char* buf, database* db, kvlist* session_data);
void inbox(FILE* out, database* db, kvlist* session_data);
void send(FILE* in, FILE* out, char* buf, database* db, kvlist* session_data);

void session(database* db, FILE* in, FILE* out) {
  kvlist* session_data = NULL;

  while (true) {
    char* buf = calloc(COMMAND_BUF_SIZE + 1, sizeof(char));
    fprintf(out, "bryant> ");
    fflush(out);
    char* got = fgets(buf, COMMAND_BUF_SIZE, in);
    if (NULL == got) {
      fputs("\n", out);
      return;
    }
    assert(strlen(buf) > 0);

    buf[strlen(buf) - 1] = '\0'; 

    char* first_word = strdup(buf);
    char* cursor = first_word;
    while ((' ' != *cursor) && ('\0' != *cursor) && ('\n' != *cursor)) {
      cursor++;
    }
    *cursor = '\0';

    if (streq(first_word, "HELP")) list_commands(out);
    else if (streq(first_word, "LIST")) list_users(out, db);
    else if (streq(first_word, "LOGIN")) {
      session_data = login(out, buf, db, session_data);
    }
    else if (streq(first_word, "INBOX")) {
      inbox(out, db, session_data);
    }
    else if (streq(first_word, "SEND")) {
      send(in, out, buf, db, session_data);
    } else {
      fputs("unrecognized command; type HELP for a list\n", out);
    }

    free(first_word);
    free(buf);
  }
  kvlist_destroy(session_data);
}

bool streq(char* left, char* right) {
  return 0 == strcmp(left, right);
}

void list_commands(FILE* out) {
  fputs("HELP: this help\n", out);
  fputs("LIST: list users\n", out);
  fputs("LOGIN username: log in\n", out);
  fputs("INBOX: see received messages\n", out);
  fputs("SEND recipient: send a message\n", out);
}

void list_users(FILE* out, database* db) {
  char* q = "SELECT username FROM users;";
  query_plan* plan = create_query_plan(parse_query(q), db);
  result* got = execute_plan(plan, NULL);

  result_row* r = got->rows;
  while (NULL != r) {
    fprintf(out, "%s\n", r->first->content);
    r = r->next;
  }
  destroy_results(got);
  destroy_plan(plan);
}

kvlist* login(FILE* out, char* buf, database* db, kvlist* session_data) {
  char* cursor = buf;
  while ((' ' != *cursor) && ('\0' != *cursor)) {
    cursor++;
  }

  assert(' ' == *cursor);
  cursor++;
  assert('\0' != *cursor);
  char* start_of_second_word = cursor;

  char* q = "SELECT username, password FROM users WHERE username = :un;";
  query_plan* plan = create_query_plan(parse_query(q), db);
  kvlist* params = kvlist_set(NULL, "un", start_of_second_word);
  result* got = execute_plan(plan, params);
  result_row* r = got->rows;
  if (NULL == r) {
    fprintf(out, "failed to log in as user '%s'; they don't exist?\n",
            start_of_second_word);
    destroy_results(got);
    destroy_plan(plan);
    return session_data;
  }

  kvlist* new_session = kvlist_set(session_data, "username", r->first->content);

  fprintf(out, "logged in as %s\n", r->first->content);

  destroy_results(got);
  destroy_plan(plan);
  return new_session;
}

void inbox(FILE* out, database* db, kvlist* session_data) {
  char* username = kvlist_get(session_data, "username");
  if (NULL == username) {
    fputs("cannot check inbox without being logged in\n", out);
    return;
  }

  char* q = "SELECT sender, message FROM messages WHERE receiver = :un;";
  query_plan* plan = create_query_plan(parse_query(q), db);
  kvlist* params = kvlist_set(NULL, "un", username);
  result* got = execute_plan(plan, params);
  result_row* r = got->rows;
  fprintf(out, "inbox for %s:\n", username);
  while (NULL != r) {
    char* sender = r->first->content;
    char* message = r->first->next->content;
    fprintf(out, "from %s: %s\n", sender, message);
    r = r->next;
  }
  fputs("end of inbox\n", out);
  destroy_results(got);
  destroy_plan(plan);
}

void send(FILE* in, FILE* out, char* buf, database* db, kvlist* session_data) {
  char* username = kvlist_get(session_data, "username");
  if (NULL == username) {
    fputs("cannot send messages without being logged in\n", out);
    return;
  }
  char* cursor = buf;
  while ((' ' != *cursor) && ('\0' != *cursor)) {
    cursor++;
  }

  assert(' ' == *cursor);
  cursor++;
  assert('\0' != *cursor);
  char* start_of_second_word = cursor;

  char* q;
  asprintf(&q, "SELECT username FROM users WHERE username = '%s';",
           start_of_second_word);
  lll(q, stderr);
  query_plan* plan = create_query_plan(parse_query(q), db);
  free(q);
  result* got = execute_plan(plan, NULL);

  result_row* r = got->rows;
  if (NULL == r) {
    fprintf(out, "couldn't find recipient %s\n", start_of_second_word);
    return;
  }

  char* recipient = r->first->content;

  fprintf(out, "enter message to %s:\n", recipient);
  fflush(out);
  char* message_buf = calloc(MESSAGE_BUF_SIZE + 1, sizeof(char));

  char* got_message = fgets(message_buf, MESSAGE_BUF_SIZE, in);
  if (NULL == got_message) {
    fputs("\nno message\n", out);
    return;
  }
  got_message[strlen(got_message) - 1] = '\0';

  FILE* outbox = fopen("/data/messages.csv", "a");
  fprintf(outbox, "\"%s\",\"%s\",\"%s\"\n",
          username,
          recipient,
          message_buf);
  fclose(outbox);
  fputs("message will be delivered later\n", out);
  return;
}
