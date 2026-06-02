# Audit checklist — 24 AI-typical defect patterns

Each entry has: a minimal code example of the defective shape, detection cues (what to grep/scan for), and false-positive guidance (what looks like the pattern but isn't).

---

## 1. swallowed-exceptions

```python
except Exception:
    return None  # or pass
```

**Detection cues:**
- `except Exception: pass` or `except: pass`.
- `except Exception:` with a justifying comment (`# Best effort`, `# Optional`). The comment explains intent without changing behavior.
- A function returning `None`, `False`, or empty default from inside an `except` block — caller can't distinguish "not found" from "broken."
- `# noqa: BLE001` annotations at scale.
- `logger.debug(...)` inside an `except` block — debug-level logging is invisible in production.
- Clusters: if you find one, check the rest of the module.

**False-positive guidance:**
- Best-effort cleanup in shutdown/`__del__`/signal handlers where raising would mask the original error.
- Narrow predicate: `except ValueError: return False` for a validation function catching one specific type.
- Optional-dependency loading: `try: import torch; except ImportError: torch = None`.
- Re-raise after logging: `except Exception as e: logger.exception(...); raise`.

---

## 2. hardcoded-config-values

```python
response = client.messages.create(model=model, max_tokens=64000, ...)
```

**Detection cues:**
- Numeric literals in API calls: `max_tokens=64000`, `timeout=30`, `chunk_size=8192`.
- String literals naming external resources: `"all-MiniLM-L6-v2"`, `"us-east-1"`.
- API calls that omit a config parameter, silently accepting the upstream library's default.
- `config.get("key", MAGIC_NUMBER)` patterns — magic-number fallback on misspelled keys.
- Two declarations of the same default (one in YAML, one in code).

**False-positive guidance:**
- True semantic constants: `MILLISECONDS_PER_SECOND = 1000`, physics constants, protocol constants (HTTP status codes).
- Values configurable through a parent layer (a function default the caller can override).
- Genuinely-best-default that users should not change (`password_min_length = 8`).

---

## 3. missing-network-timeout

```python
response = requests.get(url)  # no timeout=
```

**Detection cues:**
- `requests.get/post/put/...` without `timeout=` kwarg.
- `subprocess.run(cmd)` without `timeout=`.
- `urllib.request.urlopen(url)` without `timeout=`.
- `httpx.get(url)` (sync mode) without `timeout=`.
- Same project uses timeout at one site but not another.

**False-positive guidance:**
- Truly unbounded operations by design: `socket.accept()` on a listener.
- Framework-level timeout already covers the call (Celery `time_limit`, K8s liveness probe shorter than worst-case).
- Streaming/large-download operations with per-chunk progress checks.

---

## 4. narrating-comments

```python
# Read binary file
with open(path, 'rb') as f:
    data = f.read()
```

**Detection cues:**
- A comment immediately above a line that restates the line in English.
- Step-by-step scaffolding: `# Step 1: Load data` / `# Step 2: Process`.
- Docstrings that paraphrase the function name: `def handle_event(): """Handle an incoming event."""`
- `Args:` sections where each description is the parameter name in prose.
- `# Section Banner` comments dividing a file into named sections.

**False-positive guidance:**
- Legal/copyright comments.
- Comments explaining non-obvious constraints, workarounds, algorithms.
- Warning/TODO/FIXME comments.
- Docstrings on public API surfaces exposed to external users.

---

## 5. near-identical-siblings

```python
sub_token = None
for part in parts:
    if part.startswith('sub-'):
        sub_token = part[4:]; break

ses_token = None
for part in parts:
    if part.startswith('ses-'):
        ses_token = part[4:]; break
```

**Detection cues:**
- Three or more sequential code blocks differing only in one identifier/string/constant.
- Multiple class definitions with near-identical method bodies.
- Long `if/elif` chains testing against a fixed list with structurally identical bodies.
- Code where a `for` loop, helper function, or base class would shorten the file substantially.

**False-positive guidance:**
- Intentional unrolling for performance (SIMD, hot-path) with explanatory comment.
- Sibling structures with meaningfully divergent semantics beneath the surface similarity.
- Test code where parallel cases are written out for readability.

---

## 6. convention-drift

```python
# File A: getCompanyBySlug(...)
# File B: fetchAppBootstrap(...)
# File C: loadMorePostings(...)
```

**Detection cues:**
- Multiple sibling files/functions with different surface conventions for the same role (verb mixing, return-shape divergence, import-style mixing).
- Same-name-different-shape collisions across files.
- Mixed conventions within a single file (both relative and absolute imports; both `getX` and `fetchX`).
- Adapter/wrapper classes with split error-return or empty-value conventions.

**False-positive guidance:**
- Intentional naming that differentiates behaviors (`getX` sync vs `fetchX` network, if documented).
- Code in different languages using their respective conventions.
- Adapter internals reflecting upstream conventions while public surface is consistent.

---

## 7. inconsistent-error-handling

```python
class OllamaClient(Client):
    def chat(self, prompt):
        try: return self._call(prompt)
        except Exception as e: return f"Error: {e}"

class ClaudeClient(Client):
    def chat(self, prompt):
        return self._call(prompt)  # lets exceptions propagate
```

**Detection cues:**
- Multiple files in one directory implementing the same role with different error contracts.
- Adapter/client classes for different backends with divergent error shapes.
- Route handlers across files mixing tuple returns with wrapper-helper returns.
- A single file mixing two error-return shapes.

**False-positive guidance:**
- Genuine asymmetry between providers (one has retry logic the others don't).
- Adapter classes that look different inside but expose the same public contract.
- A documented migration between error styles with a tracking issue.

---

## 8. mutable-default-arguments

```python
def append_to(item, items=[]):
    items.append(item)
    return items
```

**Detection cues:**
- `=[]`, `={}`, `=set()`, `=dict()`, `=list()` in function signatures.
- `Optional[<container>] = <empty_container>` (type says Optional, default isn't None).
- Pydantic field with `List[str] = []` instead of `Field(default_factory=list)`.
- Function bodies calling `.pop()`, `.append()`, `.update()` on a parameter with mutable default.

**False-positive guidance:**
- Immutable defaults: `=()` (tuple), `=frozenset()`.
- Sentinel objects: `=DEFAULT` where `DEFAULT = object()`.
- Singletons by design (documented shared state).

---

## 9. assert-for-runtime-validation

```python
def create_workspace(self, resp: dict) -> Workspace:
    assert 'id' in resp
    return Workspace(id=resp['id'], status="creating")
```

**Detection cues:**
- `assert <condition>` in production code (not test code). Stripped by `python -O`.
- `assert` validating external data (API responses, user input, deserialized JSON).
- `assert isinstance(x, T)` as runtime check (not just type-narrowing).
- Functions whose error decorator doesn't catch `AssertionError`.

**False-positive guidance:**
- Test code (`test_*.py`, `*_test.py`, `tests/`).
- Type-narrowing-only asserts where a separate runtime check ensures correctness.
- Internal-invariant asserts in non-production contexts (CLI tools, notebooks).
- `@beartype` or runtime-typeguard-decorated functions.

---

## 10. async-await-mismatch

```python
# Missing await — coroutine silently discarded
self.set_progress(truncated_output)

# Unnecessary async — no await in body
async def handle_join(self, msg):
    self._users.add(msg.user)
```

**Detection cues:**
- `<async_fn>(...)` without `await` in an `async def` body.
- `RuntimeWarning: coroutine '...' was never awaited` in logs.
- `async def` with no `await` anywhere in the body.
- Attribute access on what should be a dict/object but is a coroutine (missing await upstream).
- Adjacent sites where one call awaits and the next doesn't.

**False-positive guidance:**
- Intentional fire-and-forget: `asyncio.create_task(coro)`.
- Async generators/iterators used with `async for`.
- Functions declared `async` to satisfy an abstract protocol requirement.
- Coroutines passed as arguments to `asyncio.gather`, `asyncio.wait`.

---

## 11. brittle-error-detection

```python
except ValueError as exc:
    if "already exists" in str(exc):
        raise DuplicateError(...) from exc
```

**Detection cues:**
- `if "<string>" in str(e)` inside an `except` block.
- Multiple cascading substring checks against one stringified exception.
- A typed exception class defined in the module but not raised at the throw site.
- `except Exception` combined with substring discrimination.
- A test asserting the same substring the production code matches.

**False-positive guidance:**
- Genuine bridging to a non-typed source (C extension, foreign-system error string).
- Logging-only substring use (metrics differentiation, not control flow).
- Asserting against documented stable error wording (rare).

---

## 12. f-string-in-logger-call

```python
logger.info(f"Processing request {request.id} for tenant {tenant_id}")
```

**Detection cues:**
- `logger.<level>(f"...")` or `logger.<level>("...".format(...))`.
- `logger.error(f"Failed: {e}")` without `raise` — drops the traceback.
- Multiple f-string log calls in one file.
- Project style guide mentions "lazy logging" but code uses f-strings.

**False-positive guidance:**
- Log calls with no variables: `logger.info(f"")` — just a string.
- Custom logging adapters or `structlog` where f-strings are appropriate.
- Test code logging deterministic strings for assertions.

---

## 13. print-instead-of-logging

```python
import logging
logger = logging.getLogger(__name__)
# ... later in the file:
print(f"Processing {len(items)} items...")
```

**Detection cues:**
- `print()` in any file that is not a `__main__` entry point.
- `print()` in code that imports `logging` or has a module-level `logger`.
- Multiple `print()` calls with zero `logger.*()` calls in the same file.
- `print(f"...{e}")` to report an exception (lost traceback).
- `print()` in MCP servers (stdout protocol corruption risk).

**False-positive guidance:**
- CLI entry-point output under `if __name__ == "__main__":`.
- Pre-logger-initialization bootstrap output.
- Notebook/REPL/script output.
- Test fixtures that print expected output for inspection.

---

## 14. resource-leak-no-context-manager

```python
audio_file = open(audio_path, "rb")
transcript = client.transcriptions.create(file=audio_file, ...)
return transcript.text  # audio_file never closed
```

**Detection cues:**
- `open(...)` not inside a `with` statement.
- `pickle.dump(obj, path.open(...))` — one-liner side-effect, no cleanup.
- Functions that return an open file handle (ownership handoff problem).
- Streaming file handles as instance variables without `__enter__`/`__exit__`.

**False-positive guidance:**
- Streaming files held by a class for its lifetime (class is itself a context manager).
- Temporary files with `delete=False` for cross-platform reasons.
- Files passed to APIs that document ownership transfer.
- PID/lock files intentionally held open for process lifetime.

---

## 15. shell-true-subprocess-injection

```python
cmd = f"wget -c {url} -O {dest_path}"
subprocess.run(cmd, shell=True)
```

**Detection cues:**
- `subprocess.run(cmd, shell=True)` where `cmd` is an f-string, `.format()`, or `+`-concatenated.
- `os.system(cmd)` / `os.popen(cmd)`.
- LLM output passed directly to subprocess.
- Safety-check imports wrapped in `try: import safety; except ImportError: pass`.

**False-positive guidance:**
- Hardcoded internal commands with no variables (`subprocess.run("ls -la", shell=True)`).
- Genuinely-needed shell features (pipes, redirections) with `shlex.quote()` on user values.
- Allow-list-validated values.

---

## 16. sleep-based-synchronization

```python
await asyncio.sleep(0.5)  # hope discovery completes
result = await harness.run_step(session.id)
```

**Detection cues:**
- `time.sleep(N)` in code callable from an async handler.
- `await asyncio.sleep(N)` before a test step that depends on setup completion.
- Comment saying "hope X completes" or "wait for Y" next to a sleep.
- Multiple tests with the same `sleep(0.5)` magic number.
- A `wait_for_X` helper polling REST when the system publishes WebSocket events.

**False-positive guidance:**
- Backoff loops with exponential delay.
- Deliberate pacing in a producer loop (sleep IS the desired cadence).
- `await asyncio.sleep(0)` to yield control to the event loop.
- Backoff after known transient failure between retries of the same operation.

---

## 17. string-built-sql

```python
cursor.execute(f"SELECT * FROM policies WHERE id = '{policy_id}'")
```

**Detection cues:**
- `cursor.execute(f"...")` / `cursor.execute(sql.format(...))` / `cursor.execute("..." + var)`.
- f-string SQL in agent tool functions (highest-trust-boundary surface).
- Multi-channel interpolation where identifiers and values are both f-stringed.
- `f"... '{var}' ..."` — single-quoted interpolation inside SQL.

**False-positive guidance:**
- Truly-trusted internal constants (`TABLE_NAME` from a module-level constant).
- Identifier interpolation that genuinely requires it (with allow-list validation).
- ORM-built queries that parameter-bind values internally.

---

## 18. swapped-args

```python
# Signature: create_datastore(path, store_name, workspace)
# Call site:
create_datastore(workspace, name, file_path)  # first and third swapped
```

**Detection cues:**
- Function calls with multiple positional arguments of the same or compatible types.
- Local variable names matching parameter names in form but not in order.
- Adjacent sibling functions calling the same library function — check both use the same ordering.
- Same function called correctly at one site and incorrectly at another.

**False-positive guidance:**
- Functions with intentionally symmetric arguments (`max(a, b)`).
- Calls using both positional and keyword arguments deliberately.
- Variadic functions (`*args`, `**kwargs`).

---

## 19. tarfile-extractall-without-filter

```python
tar.extractall(path)  # no filter= argument
```

**Detection cues:**
- `tar.extractall(path)` without `filter=` argument. Python 3.12+ should use `filter='data'`.
- `zipfile.ZipFile(path).extractall(dest)` — same class for ZIP.
- Archive-extracting code in dataset-fetching, model-registry, or paper-processing contexts.
- Functions whose archive input comes from user upload or external storage.

**False-positive guidance:**
- Genuinely-trusted archives (internal CI artifacts with crypto verification).
- Python < 3.12 codebases (the `filter=` argument isn't available — needs a manual wrapper).
- Test fixtures extracting known-content archives checked into the repo.

---

## 20. unjustified-lazy-import

```python
def process(data):
    import json  # why is this inside the function?
    return json.loads(data)
```

**Detection cues:**
- `import` or `from X import Y` inside a function body.
- Same module imported in multiple function bodies in one file.
- Clusters of lazy imports in adjacent functions.
- No comment explaining the lazy form (`# circular`, `# optional dep`).
- Lazy import of a stdlib module (`datetime`, `json`, `os`) — almost never justified.

**False-positive guidance:**
- Genuine circular-import break (verify: try hoisting to top-level).
- Optional heavy dependency (`import torch` in GPU-only path).
- Slow-import-for-CLI-startup (`import pandas` deferred so `--help` is fast).
- `if TYPE_CHECKING:` blocks (type-only imports).

---

## 21. unreachable-defensive-guard

```python
def format_result(result: UpdateResult) -> str:
    if result is None:        # no caller ever passes None
        return ""
    return f"{result.name}: {result.value}"
```

**Detection cues:**
- Guard at the top of a function whose callers already enforce the guard's negation.
- `isinstance` checks where the parameter type is already annotated.
- `if x is None: return None` at the top of an internal helper whose callers guarantee non-None.
- Defensive guards in clusters (sticky local pattern).

**False-positive guidance:**
- Public-API entry points validating user/network/file input.
- Guards added in response to a real prior incident (with commit message or comment).
- Guards on parameters with weak type information in duck-typing-heavy code.

---

## 22. weak-test-assertion

```python
assert "dashboard" in response.text.lower()  # matches page chrome, nav, footer...
```

**Detection cues:**
- Substring `in content.lower()` matches on rendered HTML where the substring is a common word.
- Multi-alternative `or` chains in assertions.
- Count-based checks with loose bounds: `count >= 1`.
- `assert result in (a, b)` accepting "either outcome" for a specific-behavior test.
- Test name promises specific verification but assertion is generic.

**False-positive guidance:**
- Intentionally permissive assertions in flaky-environment tests (marked `@pytest.mark.flaky`).
- Tests with explicit "either outcome is correct" semantics for non-deterministic algorithms.
- Smoke tests named to match their intent (`test_dashboard_does_not_crash`).

---

## 23. off-by-one

```python
def measured_fps(frames, duration_s):
    return len(frames) / duration_s  # N frames have N-1 intervals
```

**Detection cues:**
- `len(collection)` where the function computes a rate or average-over-spans (events vs intervals).
- `len(string)` used for display width (breaks on CJK, emoji).
- `range(0, len(arr) - 1)` or `range(1, len(arr))` — ask why boundary is skipped.
- `pathlib.Path.parents[N]` with N > 1 — miscount to repo root.
- Generator function where one off-by-one compounds across all outputs.

**False-positive guidance:**
- Slices/ranges correct for the intent (`arr[1:]` to skip first element).
- N-vs-N-1 correct for statistical context (population vs sample variance).
- Sliding-window operations where adjacent pairs are intended.

---

## 24. wrong-tool-for-job

```python
html = "<html><body>{}</body></html>".format(user_input)  # XSS; use Jinja2
```

**Detection cues:**
- `str.format()` or f-strings building HTML when a template engine is available.
- `os.path.join`/`os.path.exists` in new code when `pathlib` is already used elsewhere.
- `subprocess.call(..., shell=True)` for simple command invocation.
- Bulk operations using single-item primitives in a loop.
- `raise Exception(...)` when a more specific exception class exists.
- Justifying comments that don't survive verification (`# Using TAG for Valkey compat` when Valkey supports TEXT).

**False-positive guidance:**
- Defensible reasons to use a general primitive (building non-HTML strings).
- Legacy code that predates the better tool.
- Performance-driven choices in hot paths.
