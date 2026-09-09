# Skill Mechanics

Load this reference when an agent-facing document is a skill.

## Invocation choice

A **model-invoked** skill can be reached autonomously or by a user. Omit `disable-model-invocation`; its description is a permanently loaded context pointer containing distinct trigger branches. Choose this when the model should discover the discipline or another skill must invoke it.

A **user-invoked** skill is started only by a human. Set `disable-model-invocation: true`; make its description a short human-facing summary without trigger lists. Choose this when human judgment should initiate the workflow. Other skills cannot invoke it.

This is a trade between context load and cognitive load: model discovery permanently loads a pointer; user-only invocation makes the human the index.

## Splitting by invocation

Split a model-invoked skill out when it has a distinct leading word that should trigger independently, or another skill must reach it. Independent reach must justify the additional always-loaded description.

Shared reference needed by user-invoked skills cannot live behind either skill's invocation. Put it in a plain shared document that each may point to.

## Router skills

When user-invoked skills create too much cognitive load, create one user-invoked router that tells the human which one fits. It can recommend them but cannot invoke them; only the human can start a user-invoked skill.
