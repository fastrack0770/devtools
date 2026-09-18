# 0003: Promoted and in-progress skills

## Context
New skills need realistic piloting before becoming part of every deployed project.

## Decision
`.claude/skill-manifest.json` classifies every skill exactly once as promoted or in-progress. The deploy script ships only promoted skills, while the linter enforces complete, disjoint membership.

## Why
The manifest makes release status explicit and keeps pilots available for repository testing without silently expanding the public configuration.
