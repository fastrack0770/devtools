# Testing Patterns Reference

Concrete examples for the test-driven-development skill. Samples are illustrative (TypeScript/Jest-style) — translate the principle to your stack.

## RED → GREEN walkthrough

```typescript
// RED: This test fails because createTask doesn't exist yet
describe('TaskService', () => {
  it('creates a task with title and default status', async () => {
    const task = await taskService.createTask({ title: 'Buy groceries' });

    expect(task.id).toBeDefined();
    expect(task.title).toBe('Buy groceries');
    expect(task.status).toBe('pending');
    expect(task.createdAt).toBeInstanceOf(Date);
  });
});

// GREEN: Minimal implementation
export async function createTask(input: { title: string }): Promise<Task> {
  const task = {
    id: generateId(),
    title: input.title,
    status: 'pending' as const,
    createdAt: new Date(),
  };
  await db.tasks.insert(task);
  return task;
}
```

## Reproduction test for a bug fix

```typescript
// Bug: "Completing a task doesn't update the completedAt timestamp"

// Step 1: Reproduction test (must FAIL first)
it('sets completedAt when task is completed', async () => {
  const task = await taskService.createTask({ title: 'Test' });
  const completed = await taskService.completeTask(task.id);

  expect(completed.status).toBe('completed');
  expect(completed.completedAt).toBeInstanceOf(Date);  // Fails → bug confirmed
});

// Step 2: Fix
export async function completeTask(id: string): Promise<Task> {
  return db.tasks.update(id, {
    status: 'completed',
    completedAt: new Date(),  // This was missing
  });
}

// Step 3: Test passes → bug fixed, regression guarded
```

## Test sizes (resource model)

| Size | Constraints | Speed | Example |
|------|------------|-------|---------|
| **Small** | Single process, no I/O, no network, no database | Milliseconds | Pure function tests, data transforms |
| **Medium** | Multi-process OK, localhost only, no external services | Seconds | API tests with test DB, component tests |
| **Large** | Multi-machine OK, external services allowed | Minutes | E2E tests, benchmarks, staging integration |

Small tests should dominate the suite: fast, reliable, easy to debug.

## State-based vs interaction-based assertions

```typescript
// Good: Tests what the function does (state-based)
it('returns tasks sorted by creation date, newest first', async () => {
  const tasks = await listTasks({ sortBy: 'createdAt', sortOrder: 'desc' });
  expect(tasks[0].createdAt.getTime())
    .toBeGreaterThan(tasks[1].createdAt.getTime());
});

// Bad: Tests how the function works internally (interaction-based)
it('calls db.query with ORDER BY created_at DESC', async () => {
  await listTasks({ sortBy: 'createdAt', sortOrder: 'desc' });
  expect(db.query).toHaveBeenCalledWith(
    expect.stringContaining('ORDER BY created_at DESC')
  );
});
```

## DAMP over DRY

```typescript
// DAMP: Each test is self-contained and readable
it('rejects tasks with empty titles', () => {
  const input = { title: '', assignee: 'user-1' };
  expect(() => createTask(input)).toThrow('Title is required');
});

it('trims whitespace from titles', () => {
  const input = { title: '  Buy groceries  ', assignee: 'user-1' };
  const task = createTask(input);
  expect(task.title).toBe('Buy groceries');
});
```

Don't extract shared setup just to avoid repeating an input shape — shared helpers obscure what each test verifies.

## Arrange-Act-Assert

```typescript
it('marks overdue tasks when deadline has passed', () => {
  // Arrange
  const task = createTask({
    title: 'Test',
    deadline: new Date('2025-01-01'),
  });

  // Act
  const result = checkOverdue(task, new Date('2025-01-02'));

  // Assert
  expect(result.isOverdue).toBe(true);
});
```

## One assertion per concept, descriptive names

```typescript
// Good: Each test verifies one behavior, named as a specification
describe('TaskService.completeTask', () => {
  it('sets status to completed and records timestamp', ...);
  it('throws NotFoundError for non-existent task', ...);
  it('is idempotent — completing an already-completed task is a no-op', ...);
});

// Bad: Everything in one vaguely-named test
describe('TaskService', () => {
  it('works', ...);
  it('handles errors', ...);
});
```

## Anti-patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Testing implementation details | Tests break on refactor even when behavior is unchanged | Test inputs and outputs, not internal structure |
| Flaky tests (timing, order-dependent) | Erode trust in the suite | Deterministic assertions, isolated state |
| Testing framework code | Wastes time on third-party behavior | Only test YOUR code |
| Snapshot abuse | Large snapshots nobody reviews, break on any change | Use sparingly; review every snapshot change |
| No test isolation | Tests pass individually, fail together | Each test sets up and tears down its own state |
| Mocking everything | Tests pass while production breaks | Real > fake > stub > mock; mock only at slow/non-deterministic boundaries |
