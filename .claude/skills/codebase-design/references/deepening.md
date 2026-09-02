# Deepening

Use this reference to deepen a cluster of shallow modules safely.

## Dependency categories

1. **In-process**: pure computation or in-memory state without I/O. Merge the modules and test the new interface directly; no adapter is needed.
2. **Local-substitutable**: dependencies with faithful local stand-ins, such as an in-memory filesystem or local database. Test with the stand-in. Keep that seam internal rather than adding a port to the external interface.
3. **Remote but owned**: services under the project's control across a network. Define a port at the seam. Inject an HTTP, RPC, or queue adapter in production and an in-memory adapter in tests; keep the logic in one deep module.
4. **True external**: third-party services outside the project's control. Inject the external dependency as a port and supply a mock adapter in tests.

## Seam discipline

- One adapter means a hypothetical seam; two adapters mean a real one. Add a port only when at least two adapters are justified, commonly production and test.
- A deep module may have private internal seams for its own tests and one external seam for callers. Keep internal seams out of the public interface.
- Place the seam where behaviour varies, not where a framework happens to divide files.

## Testing: replace, do not layer

- Write tests at the deepened module's interface and assert observable outcomes.
- Once those tests cover the behaviour, delete old tests tied to the shallow modules.
- Preserve tests across internal refactors. A test that must change with implementation details is testing past the interface.
- Replace the old test surface rather than layering new integration tests over obsolete unit tests.
