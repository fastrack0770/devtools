# Accessibility Reference (WCAG 2.1 AA)

Detailed requirements, code patterns, and testing tools for the frontend-ui-engineering skill. Load when building interactive components or auditing a page. Samples are React/TSX — translate the principle to your framework.

## Keyboard navigation

Every interactive element must be operable by keyboard alone:

```tsx
<button onClick={handleClick}>Click me</button>        // ✓ Focusable by default
<div onClick={handleClick}>Click me</div>               // ✗ Not focusable, invisible to AT

// If a native element is truly impossible, replicate its contract — but prefer <button>
<div role="button" tabIndex={0} onClick={handleClick}
     onKeyDown={e => {
       if (e.key === 'Enter') handleClick();
       if (e.key === ' ') e.preventDefault();
     }}
     onKeyUp={e => {
       if (e.key === ' ') handleClick();
     }}>
  Click me
</div>
```

Checklist:
- [ ] Tab reaches every control in a logical order
- [ ] Enter/Space activate buttons; Escape closes overlays
- [ ] Focus is visible (never `outline: none` without a replacement)
- [ ] No keyboard traps (except intentional focus trap in modals)

## Labels and names

```tsx
// Icon-only buttons need a name
<button aria-label="Close dialog"><XIcon /></button>

// Form inputs: visible label preferred
<label htmlFor="email">Email</label>
<input id="email" type="email" />

// aria-label only when no visible label exists
<input aria-label="Search tasks" type="search" />
```

Checklist:
- [ ] Every input has a programmatically associated label
- [ ] Icon-only controls have `aria-label`
- [ ] Images have `alt` (empty `alt=""` for decorative)
- [ ] Links/buttons make sense out of context (no bare "click here")

## Focus management

```tsx
// Move focus when content changes
function Dialog({ isOpen, onClose }: DialogProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isOpen) closeRef.current?.focus();
  }, [isOpen]);

  // Trap focus inside dialog while open; restore focus on close
  return (
    <dialog open={isOpen}>
      <button ref={closeRef} onClick={onClose}>Close</button>
      {/* dialog content */}
    </dialog>
  );
}
```

Checklist:
- [ ] Opening a dialog moves focus into it; closing restores focus to the trigger
- [ ] Route changes move focus to the new page's heading or main landmark
- [ ] Dynamically revealed content receives focus or is announced

## Status and async updates

```tsx
// Announce loading state
<div className="space-y-3" aria-busy="true" aria-label="Loading tasks">
  {Array.from({ length: 3 }).map((_, i) => (
    <div key={i} className="h-12 bg-muted animate-pulse rounded" />
  ))}
</div>

// Announce empty state
<div role="status" className="text-center py-12">
  <h3>No tasks</h3>
  <p>Get started by creating a new task.</p>
  <Button onClick={onCreateTask}>Create Task</Button>
</div>
```

- [ ] Async results announced via `role="status"` / `aria-live="polite"`
- [ ] Errors announced via `role="alert"`
- [ ] Loading regions marked `aria-busy`

## Color and contrast

- [ ] Text contrast ≥ 4.5:1 (normal) / 3:1 (large text, UI components)
- [ ] Information never conveyed by color alone — pair with icon, text, or pattern
- [ ] Focus indicators meet 3:1 contrast against adjacent colors
- [ ] `prefers-reduced-motion` respected for non-essential animation

## Structure

- [ ] One `h1` per page; heading levels don't skip
- [ ] Landmarks: `main`, `nav`, `header`, `footer` (or ARIA equivalents)
- [ ] Lists are real `<ul>/<ol>` (add `role="list"` if CSS resets remove semantics in Safari)
- [ ] Language set on `<html lang>`

## Testing tools

| Tool | Use |
|---|---|
| **axe-core / @axe-core/react** | Automated rule checks in dev and CI |
| **Lighthouse accessibility audit** | Quick page-level score and findings |
| **Keyboard-only pass** | Tab through every flow — the cheapest high-value test |
| **Screen reader spot check** | VoiceOver (macOS) / NVDA (Windows) on critical flows |
| **Browser dev-tools accessibility tree** | Verify names, roles, states as exposed to AT |

Automated tools catch roughly a third of issues — the keyboard pass and screen-reader spot check are not optional for interactive components.
