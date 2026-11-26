MCU = atmega328p
F_CPU = 16000000UL
AVR_BIN ?= /usr/bin
CC = $(AVR_BIN)/avr-gcc
OBJCOPY = $(AVR_BIN)/avr-objcopy
SIZE = $(AVR_BIN)/avr-size
CFLAGS = -mmcu=$(MCU) -DF_CPU=$(F_CPU) -std=gnu11 -Os -g -Wall -Wextra -ffunction-sections -fdata-sections
LDFLAGS = -mmcu=$(MCU) -Wl,--gc-sections,-Map=build/ojo_uno.map -lm
HEADERS = $(wildcard main/*.h ../ESP8266_RTOS/main/*.h)
all: build/ojo_uno.hex
build/ojo_uno.elf: main/main.c $(HEADERS)
	mkdir -p build
	$(CC) $(CFLAGS) $< -o $@ $(LDFLAGS)
	$(SIZE) -C --mcu=$(MCU) $@
build/ojo_uno.hex: build/ojo_uno.elf
	$(OBJCOPY) -O ihex -R .eeprom $< $@
