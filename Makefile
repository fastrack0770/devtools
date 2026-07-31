# devtools — install targets for the three toolkits.
#
#   make                       show this help
#   make bash-scripts          put bash/bin on your PATH
#   make claude-config PROJECT=/path/to/project
#                              deploy the Claude Code base config into a project
#   make gnome-extension       install the Claude Usage GNOME Shell extension
#   make install [PROJECT=…]   all of the above (claude-config only if PROJECT is set)

SHELL := /bin/bash
DEPLOY := $(CURDIR)/deploy
UUID := claude-usage@claude-usage-control
EXT_DIR := $(HOME)/.local/share/gnome-shell/extensions/$(UUID)

PROJECT ?=

.DEFAULT_GOAL := help
.PHONY: help install bash-scripts claude-config gnome-extension uninstall-gnome-extension

help:
	@echo "devtools — available targets:"
	@echo
	@echo "  make bash-scripts                        add bash/bin to PATH in your shell rc"
	@echo "  make claude-config PROJECT=<dir>         deploy the Claude Code base config into <dir>"
	@echo "  make gnome-extension                     install the Claude Usage GNOME Shell extension"
	@echo "  make uninstall-gnome-extension           remove and disable that extension"
	@echo
	@echo "  make install [PROJECT=<dir>]             all three (claude-config only with PROJECT)"

## 1. Console utilities — bash/bin on PATH.
bash-scripts:
	$(DEPLOY)/bash-scripts.sh

## 2. Claude Code configuration — skills, commands, hooks, CLAUDE.md.
claude-config:
	@if [ -z "$(PROJECT)" ]; then \
		echo "Usage: make claude-config PROJECT=/path/to/project" >&2; \
		exit 1; \
	fi
	$(DEPLOY)/claude-config.sh "$(PROJECT)"

## 3. Ubuntu (GNOME Shell) extension — Claude usage indicator.
gnome-extension:
	$(DEPLOY)/gnome-extension.sh

uninstall-gnome-extension:
	-gnome-extensions disable $(UUID) 2>/dev/null
	rm -rf "$(EXT_DIR)"
	@echo "Removed $(EXT_DIR) — log out and back in to drop it from the panel."

install: bash-scripts gnome-extension
ifneq ($(PROJECT),)
install: claude-config
else
	@echo
	@echo "Note: PROJECT was not set, so the Claude Code config was not deployed."
	@echo "      Run: make claude-config PROJECT=/path/to/project"
endif
