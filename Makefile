# devtools — install targets for the three toolkits.
#
#   make                                          show this help
#   make install                                  everything (claude-config needs PROJECT)
#   make install bash-scripts                     put bash/bin on your PATH
#   make install gnome-extension                  install the AI Usage GNOME Shell extension
#   make install claude-config PROJECT=<dir>      deploy the Claude Code base config into <dir>
#   make install bash-scripts gnome-extension     several components at once
#
#   make uninstall bash-scripts                   take bash/bin back off your PATH
#   make uninstall gnome-extension                remove and disable that extension

SHELL := /bin/bash
DEPLOY := $(CURDIR)/deploy
UUID := ai-usage@ai-usage-control
# pre-rename identity; uninstall clears it too so no stale bar is left behind
OLD_UUID := claude-usage@claude-usage-control
EXT_ROOT := $(HOME)/.local/share/gnome-shell/extensions
EXT_DIR := $(EXT_ROOT)/$(UUID)

PROJECT ?=

COMPONENTS := bash-scripts claude-config gnome-extension
UNINSTALLABLE := bash-scripts gnome-extension

## `make install <component>…` / `make uninstall <component>…`
##
## The words after install/uninstall are arguments, but make still treats them as
## goals and would build them a second time. So they get no-op stubs here, and the
## real recipes live under the do-* / undo-* names that nobody types.
VERB := $(firstword $(MAKECMDGOALS))
ifneq ($(filter install uninstall,$(VERB)),)
SELECTED := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
ifeq ($(VERB),uninstall)
VALID := $(UNINSTALLABLE)
else
VALID := $(COMPONENTS)
endif
UNKNOWN := $(filter-out $(VALID),$(SELECTED))
ifneq ($(UNKNOWN),)
$(error unknown component '$(UNKNOWN)' for '$(VERB)' — valid: $(VALID))
endif
ifneq ($(SELECTED),)
$(eval $(SELECTED): ; @:)
.PHONY: $(SELECTED)
endif
else
SELECTED :=
# Back-compat: the old bare forms (`make claude-config PROJECT=…`) still work.
$(foreach c,$(COMPONENTS),$(eval $(c): do-$(c)))
.PHONY: $(COMPONENTS)
endif

# Bare `make install` means everything — but only deploy the Claude config when
# PROJECT was given, since it has nowhere to go otherwise.
ifeq ($(SELECTED),)
INSTALL_TARGETS := do-bash-scripts do-gnome-extension $(if $(PROJECT),do-claude-config)
UNINSTALL_TARGETS := $(addprefix undo-,$(UNINSTALLABLE))
else
INSTALL_TARGETS := $(addprefix do-,$(SELECTED))
UNINSTALL_TARGETS := $(addprefix undo-,$(SELECTED))
endif

.DEFAULT_GOAL := help
.PHONY: help install uninstall \
        $(addprefix do-,$(COMPONENTS)) $(addprefix undo-,$(UNINSTALLABLE))

help:
	@echo "devtools — usage: make install [component…]"
	@echo
	@echo "  make install                                install everything"
	@echo "  make install bash-scripts                   add bash/bin to PATH in your shell rc"
	@echo "  make install gnome-extension                install the AI Usage GNOME Shell extension"
	@echo "  make install claude-config PROJECT=<dir>    deploy the Claude Code base config into <dir>"
	@echo
	@echo "  Components combine: make install bash-scripts gnome-extension"
	@echo "  Bare 'make install' skips claude-config unless PROJECT is set."
	@echo
	@echo "  make uninstall bash-scripts                 take bash/bin back off your PATH"
	@echo "  make uninstall gnome-extension              remove and disable that extension"

install: $(INSTALL_TARGETS)
ifeq ($(SELECTED),)
ifeq ($(PROJECT),)
	@echo
	@echo "Note: PROJECT was not set, so the Claude Code config was not deployed."
	@echo "      Run: make install claude-config PROJECT=/path/to/project"
endif
endif

uninstall: $(UNINSTALL_TARGETS)

# Back-compat for the old hyphenated form.
.PHONY: uninstall-gnome-extension
uninstall-gnome-extension: undo-gnome-extension

## 1. Console utilities — bash/bin on PATH.
do-bash-scripts:
	$(DEPLOY)/bash-scripts.sh

## 2. Claude Code configuration — skills, commands, hooks, CLAUDE.md.
do-claude-config:
	@if [ -z "$(PROJECT)" ]; then \
		echo "Usage: make install claude-config PROJECT=/path/to/project" >&2; \
		exit 1; \
	fi
	$(DEPLOY)/claude-config.sh "$(PROJECT)"

## 3. Ubuntu (GNOME Shell) extension — Claude Code and Codex usage indicators.
do-gnome-extension:
	$(DEPLOY)/gnome-extension.sh

undo-bash-scripts:
	$(DEPLOY)/bash-scripts-uninstall.sh

undo-gnome-extension:
	-gnome-extensions disable $(UUID) 2>/dev/null
	-gnome-extensions disable $(OLD_UUID) 2>/dev/null
	rm -rf "$(EXT_DIR)" "$(EXT_ROOT)/$(OLD_UUID)"
	@echo "Removed $(EXT_DIR) — log out and back in to drop it from the panel."
