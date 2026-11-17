CC = gcc
CFLAGS = -O2 -Wall -Wextra -Wpedantic -std=c99 -DSTBI_ONLY_PNG
LIBS = -lwayland-client -lwayland-egl -lEGL -lGLESv2 -lm
TARGET = aurora-wallpaper
SRCS = main.c gl_utils.c wlr-layer-shell-unstable-v1-protocol.c xdg-shell-protocol.c
OBJS = $(SRCS:.c=.o)
DATA_DIR = $(HOME)/.local/share/aurora-wallpaper

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) $(LIBS) -o $(TARGET)

%.o: %.c shader.h gl_utils.h wlr-layer-shell-unstable-v1-client-protocol.h xdg-shell-client-protocol.h
	$(CC) $(CFLAGS) -c $< -o $@

install: $(TARGET)
	mkdir -p $(HOME)/.local/bin $(DATA_DIR)/blackwall
	install -m 755 $(TARGET) $(HOME)/.local/bin/$(TARGET)
	install -m 644 ../../ressource/lucy.png $(DATA_DIR)/lucy.png
	install -m 644 ../../ressource/blackwall/blackwall_mask.png $(DATA_DIR)/blackwall/blackwall_mask.png

clean:
	rm -f $(TARGET) $(OBJS)

.PHONY: all clean install
