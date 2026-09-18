---
name: wizard
description: Generate an interactive Bash wizard for manual procedures. Use when provisioning infrastructure, setting up credentials or CI secrets, walking an unfamiliar third-party dashboard, or guiding a one-off migration or cutover that a human must click through. Not for steps the agent can perform itself.
---

# Wizard

A wizard is an interactive Bash script that guides a human through a manual procedure, opens relevant pages, captures values, writes them to their destinations, and confirms progress stage by stage. Scope and author only the procedure-specific stages; preserve the library above the `STAGES` marker in `scripts/template.sh`.

Wizards are ephemeral by default: place one in a scratch or `scripts/` path and remove it after use. Keep it in the repository only when the user wants a repeatable setup path.

## 1. Scope the procedure

Read the repository before asking questions. For setup, inspect `.env*`, README files, compose and framework configuration, and `.github/workflows/*`, including every `secrets.*` and `vars.*` reference. For migrations or cutovers, establish current state, target state, dependencies, and irreversible actions.

Show the user the ordered stages and each value produced, then confirm the scope.

**Done when:** every stage is named in order, and every captured value has a known source, destination, and secret/public classification.

## 2. Map each stage's journey

Write the concrete human path for each stage: URL, navigation, action, value location, and destination variable. Check current official documentation or ask the user whenever the interface or command is uncertain. Never invent UI steps you do not know.

**Done when:** every stage contains precise instructions a stranger can follow without guessing.

## 3. Author the wizard

Copy `scripts/template.sh` to the target path. Keep everything above the `STAGES` marker unchanged, replace the example stage with one focused `stage` per step in dependency order, and set `TOTAL_STAGES` accurately.

Use `stage`, `say`/`step`, `open_url`, `ask`/`ask_secret`, `write_env`, `set_secret`/`set_var`, and `pause`/`confirm`. Use `ask_secret` for every secret, write each persisted value to its declared destination, send only required CI values to `set_secret`, and place `confirm` before every irreversible action.

**Done when:** the script implements every mapped stage, captures every value safely, and preserves the template library and `STAGES` convention.

## 4. Verify and hand off

Run `bash -n <script>` and `shellcheck <script>` when shellcheck is available, then `chmod +x <script>`. Never run the wizard end to end yourself because it opens browsers and blocks on human input. Trace it statically: every scoped value is captured and reaches its stated destination, every GitHub secret matches a workflow reference, and irreversible actions have confirmation gates.

Tell the user how to run it. For a repeatable setup path, link it from the project's documentation.

**Done when:** syntax and available static checks pass, the script is executable, the static trace is complete, and the user has the run command.

## Verification

The library above `STAGES` is unchanged; stage count and order match the agreed scope; secret and irreversible-action guardrails hold; instructions are sourced rather than invented; syntax and available shell checks pass; and the wizard was not run end to end by the agent.
