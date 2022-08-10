CC=clang
CFLAGS=-O0 -emit-llvm -c -fno-stack-protector
TARGET = authentication
all: $(TARGET)

$(TARGET): $(TARGET).c
	$(CC) $(CFLAGS) -o $(TARGET) $(TARGET).c
clean:
	rm -f $(TARGET)
