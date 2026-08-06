# Performance Reference: Patterns, Budgets, Checklist

Detailed material for the performance-optimization skill. Load the section matching the bottleneck you measured. Code samples are illustrative (TypeScript/React/Express) — translate the principle to your stack.

## N+1 queries

```typescript
// BAD: N+1 — one query per task for the owner
const tasks = await db.tasks.findMany();
for (const task of tasks) {
  task.owner = await db.users.findUnique({ where: { id: task.ownerId } });
}

// GOOD: Single query with join/include
const tasks = await db.tasks.findMany({
  include: { owner: true },
});
```

## Unbounded data fetching

```typescript
// BAD: Fetching all records
const allTasks = await db.tasks.findMany();

// GOOD: Paginated with limits
const tasks = await db.tasks.findMany({
  take: 20,
  skip: (page - 1) * 20,
  orderBy: { createdAt: 'desc' },
});
```

## Image optimization

```html
<!-- BAD: No dimensions, no format optimization -->
<img src="/hero.jpg" />

<!-- GOOD: Hero / LCP image — art direction + resolution switching, high priority -->
<picture>
  <!-- Mobile: portrait crop -->
  <source
    media="(max-width: 767px)"
    srcset="/hero-mobile-400.avif 400w, /hero-mobile-800.avif 800w"
    sizes="100vw" width="800" height="1000" type="image/avif"
  />
  <source
    media="(max-width: 767px)"
    srcset="/hero-mobile-400.webp 400w, /hero-mobile-800.webp 800w"
    sizes="100vw" width="800" height="1000" type="image/webp"
  />
  <!-- Desktop: landscape crop -->
  <source
    srcset="/hero-800.avif 800w, /hero-1200.avif 1200w, /hero-1600.avif 1600w"
    sizes="(max-width: 1200px) 100vw, 1200px" width="1200" height="600" type="image/avif"
  />
  <source
    srcset="/hero-800.webp 800w, /hero-1200.webp 1200w, /hero-1600.webp 1600w"
    sizes="(max-width: 1200px) 100vw, 1200px" width="1200" height="600" type="image/webp"
  />
  <img src="/hero-desktop.jpg" width="1200" height="600" fetchpriority="high" alt="Hero image description" />
</picture>

<!-- GOOD: Below-the-fold image — lazy loaded + async decoding -->
<img src="/content.webp" width="800" height="400" loading="lazy" decoding="async" alt="Content image description" />
```

Always set `width`/`height` (prevents CLS). Use `fetchpriority="high"` only on the LCP image.

## Unnecessary re-renders (React)

```tsx
// BAD: New object on every render forces children to re-render
function TaskList() {
  return <TaskFilters options={{ sortBy: 'date', order: 'desc' }} />;
}

// GOOD: Stable reference
const DEFAULT_OPTIONS = { sortBy: 'date', order: 'desc' } as const;
function TaskList() {
  return <TaskFilters options={DEFAULT_OPTIONS} />;
}

// React.memo for measured-expensive components
const TaskItem = React.memo(function TaskItem({ task }: Props) {
  return <div>{/* expensive render */}</div>;
});

// useMemo for measured-expensive computations
function TaskStats({ tasks }: Props) {
  const stats = useMemo(() => calculateStats(tasks), [tasks]);
  return <div>{stats.completed} / {stats.total}</div>;
}
```

Memoize what profiling shows is expensive — blanket memoization adds overhead and hides real problems.

## Bundle size

```typescript
// Modern bundlers (Vite, webpack 5+) tree-shake named imports automatically,
// provided the dependency ships ESM with `sideEffects: false`.
// Profile before changing import styles — real gains come from splitting and lazy loading.

// Dynamic import for heavy, rarely-used features
const ChartLibrary = lazy(() => import('./ChartLibrary'));

// Route-level code splitting wrapped in Suspense
const SettingsPage = lazy(() => import('./pages/Settings'));

function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <SettingsPage />
    </Suspense>
  );
}
```

## Caching (backend)

```typescript
// Cache frequently-read, rarely-changed data
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
let cachedConfig: AppConfig | null = null;
let cacheExpiry = 0;

async function getAppConfig(): Promise<AppConfig> {
  if (cachedConfig && Date.now() < cacheExpiry) {
    return cachedConfig;
  }
  cachedConfig = await db.config.findFirst();
  cacheExpiry = Date.now() + CACHE_TTL;
  return cachedConfig;
}

// HTTP caching for static assets (content-hashed filenames)
app.use('/static', express.static('public', {
  maxAge: '1y',
  immutable: true,
}));

// Cache-Control for API responses
res.set('Cache-Control', 'public, max-age=300');
```

## Measurement snippets

```typescript
// RUM: Web Vitals in code
import { onLCP, onINP, onCLS } from 'web-vitals';
onLCP(console.log);
onINP(console.log);
onCLS(console.log);
```

```typescript
// Simple backend timing
console.time('db-query');
const result = await db.query(...);
console.timeEnd('db-query');
```

Core Web Vitals thresholds:

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| **LCP** | ≤ 2.5s | ≤ 4.0s | > 4.0s |
| **INP** | ≤ 200ms | ≤ 500ms | > 500ms |
| **CLS** | ≤ 0.1 | ≤ 0.25 | > 0.25 |

## Example performance budget

A starting point — tune per project and record the agreed numbers in the project docs:

```
JavaScript bundle: < 200KB gzipped (initial load)
CSS: < 50KB gzipped
Images: < 200KB per above-the-fold image
Fonts: < 100KB total
API response time: < 200ms (p95)
Time to Interactive: < 3.5s on 4G
Lighthouse Performance score: ≥ 90
```

Enforce in CI:

```bash
npx bundlesize --config bundlesize.config.json
npx lhci autorun
```

## Pre-merge performance checklist

- [ ] Before and after measurements exist (specific numbers)
- [ ] The specific bottleneck is identified and addressed
- [ ] Core Web Vitals within "Good" thresholds (user-facing changes)
- [ ] Bundle size hasn't grown unexpectedly
- [ ] No N+1 queries or unpaginated list endpoints in new data fetching
- [ ] Performance budget passes in CI (if configured)
- [ ] Existing tests still pass
