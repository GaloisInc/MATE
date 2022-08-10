#include <stdio.h>
#include <stdlib.h>

void __attribute__((noinline)) observe(char *p) __attribute__((optnone)) {
  for (int i = 0; i < 255; i++) {
    printf("%c", p[i]);
  }
}

void __attribute__((noinline)) true_positive_intraprocedural_load(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return;
  }
  if (atoi(getenv("0")) == 3) {
    free(buf);
  }
  printf("%c", buf[0]);
}

void __attribute__((noinline)) true_positive_intraprocedural_store(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return;
  }
  if (atoi(getenv("0")) == 3) {
    free(buf);
  }
  buf[0] = 32;
  observe(buf);
}

void __attribute__((noinline)) true_positive_intraprocedural_loop_load(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return;
  }
  for (int i = 0; i < 255; ++i) {
    printf("%c", buf[i]);
    free(buf);
  }
}

void __attribute__((noinline)) true_positive_intraprocedural_loop_store(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return;
  }
  for (int i = 0; i < 255; ++i) {
    buf[i] = 32;
    observe(buf);
    free(buf);
  }
}

void __attribute__((noinline)) false_positive_intraprocedural_loop_load(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return;
  }
  for (int i = 0; i < 255; ++i) {
    printf("%c", buf[i]);
    if (i == 254) {
      free(buf);
    }
  }
}

void __attribute__((noinline)) false_positive_intraprocedural_loop_store(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return;
  }
  for (int i = 0; i < 255; ++i) {
    buf[i] = 32;
    if (i == 254) {
      free(buf);
    }
  }
  observe(buf);
}

void __attribute__((noinline))
true_negative_intraprocedural_no_free_load(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return;
  }
  if (atoi(getenv("0")) == 3) {
    printf("%c\n", buf[0]);
  }
}

void __attribute__((noinline))
true_negative_intraprocedural_no_free_store(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return;
  }
  if (atoi(getenv("0")) == 3) {
    buf[0] = 32;
  }
  observe(buf);
}

void __attribute__((noinline))
true_negative_intraprocedural_free_after_use_load(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return;
  }
  if (atoi(getenv("0")) == 3) {
    printf("%c\n", buf[0]);
  }
  free(buf);
}

void __attribute__((noinline))
true_negative_intraprocedural_free_after_use_store(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return;
  }
  if (atoi(getenv("0")) == 3) {
    buf[0] = 32;
  }
  observe(buf);
  free(buf);
}

char *__attribute__((noinline)) false_negative_interprocedural(void) {
  FILE *fp;
  char *buf = (char *)malloc(255);
  fp = fopen("test.txt", "r");
  char *ret = fgets(buf, 255, fp);
  if (ret == NULL) {
    return NULL;
  }
  if (atoi(getenv("0")) == 3) {
    free(buf);
  }
  return buf;
}

char interprocedural_use_load(char *buf) {
  printf("%s", buf);
  return buf[2];
}

char interprocedural_use_store(char *buf) {
  printf("%s", buf);
  return buf[2];
}

int main() {
  true_positive_intraprocedural_load();
  true_positive_intraprocedural_store();
  true_positive_intraprocedural_loop_load();
  true_positive_intraprocedural_loop_store();
  false_positive_intraprocedural_loop_load();
  false_positive_intraprocedural_loop_store();
  true_negative_intraprocedural_no_free_load();
  true_negative_intraprocedural_no_free_store();
  true_negative_intraprocedural_free_after_use_load();
  true_negative_intraprocedural_free_after_use_store();
  interprocedural_use_load(false_negative_interprocedural());
  interprocedural_use_store(false_negative_interprocedural());
  return 0;
}
