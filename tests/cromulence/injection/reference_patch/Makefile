BUILD_DIR ?= ./build
SRC_DIR ?= ./src
PRIV_DIR ?= ./priv

TARGET ?= bryant.bin

CC := clang-7

CPPFLAGS ?= -MD
CFLAGS ?= -g -Wall -Werror
LDFLAGS ?= -g

HARDCODED_SRCS = $(wildcard $(SRC_DIR)/*.c)

SRCS := $(HARDCODED_SRCS)
OBJS := $(SRCS:$(SRC_DIR)/%.c=$(BUILD_DIR)/%.o)
DEPS := $(OBJS:.o=.d)

$(BUILD_DIR)/$(TARGET): $(OBJS)
	$(CC) $(OBJS) -o $@ $(LDFLAGS)

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c
	mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

.PHONY: clean docker

run: $(BUILD_DIR)/$(TARGET)
	$<

clean:
	rm -rf $(BUILD_DIR)

docker:
	docker build -t bryant .
	docker run --cap-add=SYS_PTRACE --security-opt seccomp=unconfined --rm -it -v `pwd`:/mnt bryant

-include $(DEPS)
