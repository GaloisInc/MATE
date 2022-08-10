BUILD_DIR ?= ./build

TARGET ?= hello.bin

CPPFLAGS ?= -MD
CFLAGS ?= -g3 -grecord-gcc-switches -Wall -Werror
LDFLAGS ?= -g

SRCS := hello.c
OBJS := $(SRCS:%.c=$(BUILD_DIR)/%.o)

$(BUILD_DIR)/$(TARGET): $(OBJS)
	clang-7 $(OBJS) -o $@ $(LDFLAGS)

$(BUILD_DIR)/%.o: %.c
	mkdir -p $(dir $@)
	clang-7 $(CPPFLAGS) $(CFLAGS) -c $< -o $@

.PHONY: clean

run: $(BUILD_DIR)/$(TARGET)
	$<

clean:
	rm -rf $(BUILD_DIR)
