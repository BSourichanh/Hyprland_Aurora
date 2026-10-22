CC = gcc
CFLAGS = -O3 -march=native -Wall -Wextra -std=c99
LIBS = -lwayland-client -lwayland-egl -lEGL -lGLESv2 -lm
TARGET = aurora-wallpaper
SRCS = main.c wlr-layer-shell-unstable-v1-protocol.c xdg-shell-protocol.c

all: $(TARGET)

$(TARGET): $(SRCS) shader.h stb_image.h
	$(CC) $(CFLAGS) $(SRCS) $(LIBS) -o $(TARGET)

install: $(TARGET)
	mkdir -p $(HOME)/.local/bin
	install -m 755 $(TARGET) $(HOME)/.local/bin/$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all clean install
