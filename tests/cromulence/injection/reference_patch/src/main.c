#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <unistd.h>

#include "db.h"
#include "execute.h"
#include "lex.h"
#include "log.h"
#include "plan.h"
#include "query_parser.h"
#include "session.h"

void test(database* db) {
#ifndef NO_LOG
  dump_database(stderr, db);
#endif

  char* q = "SElecT password FROM users WHERE username = 'jerry' or username = :un UNION SELECT * from secret;";
  ast* test_query = parse_query(q);
  query_plan* test_plan = create_query_plan(test_query, db);
#ifndef NO_LOG
  dump_plan(stderr, test_plan);
#endif
  kvlist* test_params = kvlist_set(NULL, "un", "george");
  result* test_results = execute_plan(test_plan, test_params);
#ifndef NO_LOG
  dump_results(stderr, test_results);
#endif
  destroy_results(test_results);
  test_results = NULL;
  destroy_plan(test_plan);
  test_plan = NULL;
  kvlist_destroy(test_params);
  test_params = NULL;
}

int main() {
  lll("loading database\n");
  database* db = load_database("/data");

  lll("loaded database\n");

  test(db);

  if (NULL == getenv("PORT")) {
    lll("launching in stdio mode\n");

    session(db, stdin, stdout);
  } else {
    int port = atoi(getenv("PORT"));
    lll("Launching on tcp port %d\n", port);

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    int sock_got = setsockopt(sock, SOL_SOCKET,
                              SO_REUSEADDR | SO_REUSEPORT,
                              &opt, sizeof(opt));
    if (0 != sock_got) {
      lll("Got %x from setsockopt, expected 0\n", sock_got);
      exit(-1);
    }

    struct sockaddr_in address;
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);
    int bind_got = bind(sock,
                        (const struct sockaddr*) &address, sizeof(address));
    if (0 != bind_got) {
      lll("Got %x from bind, expected 0\n", bind_got);
      exit(-1);
    }

    int listen_got = listen(sock, 1);
    if (0 != listen_got) {
      lll("Got %x from listen_got, expected 0\n", listen_got);
      exit(-1);
    }
    lll("listening\n");

    struct sockaddr client_address;
    socklen_t client_address_len = sizeof(client_address);

    int client_fd = accept(sock,
                           &client_address,
                           &client_address_len);

    FILE* net_in = fdopen(dup(client_fd), "r");
    FILE* net_out = fdopen(dup(client_fd), "w");

    session(db, net_in, net_out);

    fclose(net_out);
    fclose(net_in);
    close(client_fd);
  }

  return 0;
}
