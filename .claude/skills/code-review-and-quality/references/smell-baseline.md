# Smell Baseline

The repository's documented standard overrides this baseline. Every smell is a judgement call, never a hard violation; skip anything tooling enforces.

Each entry states what it is → how to fix it.

- **Mysterious Name:** a function, variable, or type whose name does not reveal its purpose → rename it; if no honest name comes, clarify the design.
- **Duplicated Code:** the same logic shape appears in multiple hunks or files → extract the shared shape and call it from both.
- **Feature Envy:** a method reaches into another object's data more than its own → move the method onto the data it envies.
- **Data Clumps:** the same fields or parameters repeatedly travel together → bundle them into one type.
- **Primitive Obsession:** a primitive or string represents a domain concept → give the concept its own small type.
- **Repeated Switches:** the same switch or conditional cascade recurs on the same type → use polymorphism or a shared map.
- **Shotgun Surgery:** one logical change requires scattered edits across many files → gather what changes together into one module.
- **Divergent Change:** one file or module changes for unrelated reasons → split it so each module changes for one reason.
- **Speculative Generality:** abstractions, parameters, or hooks serve needs absent from the spec → delete them and inline until a real need appears.
- **Message Chains:** long navigation such as `a.b().c().d()` exposes structure the caller should not know → hide the walk behind one method on the first object.
- **Middle Man:** a class or function mostly delegates onward → remove it and call the real target directly.
- **Refused Bequest:** a subclass or implementer ignores or overrides most inherited behavior → replace inheritance with composition.
