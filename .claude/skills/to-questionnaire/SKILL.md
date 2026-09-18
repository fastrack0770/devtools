---
name: to-questionnaire
description: Turn a decision the user cannot answer alone into a questionnaire for someone else.
disable-model-invocation: true
---

# To Questionnaire

Turn a knowledge gap into a Markdown questionnaire for one recipient to answer asynchronously or in a meeting. Grill the send, not the subject: ask only what the user can answer about the recipient and the outcome they need.

## 1. Identify the recipient

Ask in one exchange for the recipient's role, expertise, and relationship to the user. This sets the tone and the context the document must carry.

**Done when:** you know who will answer and what they know that the user does not.

## 2. Define what must come back

Ask in one exchange for the specific facts or decisions the user cannot resolve alone. Translate them into a concrete list of what the user must be able to do or decide afterward.

**Done when:** the required outcomes are explicit and testable.

## 3. Write the questionnaire

Create `to-questionnaire-<slug>.md` in the current directory, with a topic-derived slug. Do not put secrets or personal data about third parties into the questionnaire.

Use this structure:

```markdown
# <Questionnaire title>

**Purpose:** <why this exists and the decision riding on it>
**From:** <user>  
**To:** <recipient>  
**How your answers will be used:** <where they go>

## Context
<One orienting paragraph, concise but sufficient.>

## How to answer
<Deadline, rough effort, and permission for partial or uncertain answers.>

## <Most important theme>
### <One idea per question?>
_Why this matters: <only when needed to prevent misreading>_

>

## Anything else?
<Anything we did not ask that we should know?>
```

Group more than a handful of questions into themed `##` sections, most important first. Give every question its own answer stub and keep compound questions separate.

**Done when:** the file exists, every required outcome has a question, and the path is reported.

## Verification

The questionnaire identifies purpose, sender, recipient, and use; supplies enough context and answer guidance; orders themed questions by importance; uses one idea and one answer stub per question; ends with `Anything else?`; and contains no secrets or third-party personal data.
