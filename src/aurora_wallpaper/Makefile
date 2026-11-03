CC = gcc
CFLAGS = -O3 -march=native -Wall -Wextra -std=c99
LIBS = -lwayland-client -lwayland-egl -lEGL -lGLESv2 -lm
TARGET = aurora-wallpaper
SRCS = main.c gl_utils.c wlr-layer-shell-unstable-v1-protocol.c xdg-shell-protocol.c
OBJS = $(SRCS:.c=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) $(LIBS) -o $(TARGET)

%.o: %.c shader.h gl_utils.h
	$(CC) $(CFLAGS) -c $< -o $@

install: $(TARGET)
	mkdir -p $(HOME)/.local/bin
	install -m 755 $(TARGET) $(HOME)/.local/bin/$(TARGET)

clean:
	rm -f $(TARGET) $(OBJS)

.PHONY: all clean install
