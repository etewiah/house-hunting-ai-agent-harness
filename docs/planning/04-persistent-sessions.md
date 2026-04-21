# 04 — Persistent Sessions

## Goal

Every time a buyer runs `uv run house-hunt`, the harness starts from scratch. The
buyer re-types their brief, waits for listings to be fetched and ranked, and loses
any shortlisting decisions they made in a previous session. For a serious buyer who
may run 10–20 sessions over several weeks, this is genuinely painful: they lose track
of properties they dismissed, properties they liked but wanted to revisit, and any
notes they added.

Persistent sessions solve this by:

1. **Resuming from where the buyer left off.** A session stores the buyer profile,
   the shortlist, the search history, and per-listing notes. Running `house-hunt
   --resume` brings all of this back.
2. **Tracking what changed.** If a shortlisted property's price drops between sessions,
   the buyer should be told. If a listing disappears, the session notes it.
3. **Syncing to HomesToCompare quests.** An H2C quest (`/mq/[id]`) is the natural
   persistent container for a house-hunting journey. The harness creates a quest on
   first run and syncs the shortlist to it on each subsequent run. The buyer can view
   their shortlist on the H2C website from any device.

The feature has two backends: a local JSON file (`~/.house-hunt/sessions/`) for users
without H2C credentials, and an H2C quest for users who are signed in. The local file
is the default; H2C quest sync is opt-in.

---

## HomesToCompare Integration

H2C "quests" at `/mq/[id]` represent a buyer's house-hunting journey. A quest groups
a set of listings, stores buyer notes, and tracks the comparison history.

**Integration points:**

1. **Quest creation.** On first run (when `H2C_BASE_URL` and `H2C_HARNESS_KEY` are
   configured), the harness calls a new H2C endpoint to create a quest and receives
   a `quest_id`. This ID is stored in the local session file.

2. **Shortlist sync.** Each time the buyer shortlists a listing (or removes one), the
   harness syncs the current shortlist to the quest via a PATCH or POST call.

3. **Quest read.** On `--resume`, the harness fetches the quest from H2C to pull any
   changes the buyer made via the H2C website (e.g. adding a note via the H2C UI).

4. **Quest URL as the shareable session link.** The buyer can send
   `https://homestocompare.com/mq/[id]` to their partner, mortgage broker, or
   conveyancer. This is the primary sharing mechanism for the session.

The local session file acts as a fallback and a local cache. The H2C quest is the
source of truth when available, but the harness must work offline (with the local
file) when H2C is unreachable.

---

## External APIs / Services

No external third-party APIs are needed for this feature. All persistence is handled
by:

- **Local filesystem:** Python `json` module, `pathlib.Path`, no dependencies.
- **H2C quest API:** The existing `HomesToCompareConnector` extended with quest
  endpoints.

Optional dependencies for Phase 4:

- **SQLite via Python `sqlite3` stdlib:** An alternative local backend for users who
  have many sessions and want indexed queries.
- **`platformdirs` package:** Platform-appropriate location for the session directory
  (`~/.house-hunt/` on Linux/macOS, `%APPDATA%\house-hunt\` on Windows).
  Already likely available via the project's dependency tree.

---

## Data Model Changes

### New `ListingNote` dataclass

```python
@dataclass
class ListingNote:
    listing_id: str
    text: str
    created_at: str          # ISO 8601 datetime string
    updated_at: str          # ISO 8601 datetime string
    source: str              # "cli", "mcp", "h2c_web"
```

### New `ShortlistEntry` dataclass

```python
@dataclass
class ShortlistEntry:
    listing: Listing
    added_at: str            # ISO 8601 datetime string
    ranked_score: float      # Score at the time of shortlisting
    notes: list[ListingNote]
    status: str              # "active" | "viewing_booked" | "offer_made" | "rejected"
```

### New `SearchRecord` dataclass

```python
@dataclass
class SearchRecord:
    session_id: str
    brief: str               # Raw buyer brief text for this run
    timestamp: str           # ISO 8601 datetime string
    result_count: int
    top_listing_ids: list[str]   # IDs of top 5 results
```

### New `Session` dataclass

```python
@dataclass
class Session:
    session_id: str              # UUID4
    created_at: str              # ISO 8601 datetime string
    updated_at: str              # ISO 8601 datetime string
    buyer_profile: BuyerProfile
    shortlist: list[ShortlistEntry]
    search_history: list[SearchRecord]
    h2c_quest_id: str | None     # Populated when H2C quest is created
    h2c_quest_url: str | None    # Full URL to the quest page
    version: int                 # Schema version for future migration
```

### Changes to `SessionState`

`SessionState` in `src/harness/session_state.py` is a transient in-memory object
for a single harness run. It gains a reference to the persistent `Session`:

```python
@dataclass
class SessionState:
    buyer_profile: BuyerProfile | None = None
    ranked_listings: list[RankedListing] = field(default_factory=list)
    triage_warnings: list[str] = field(default_factory=list)
    approvals: list[str] = field(default_factory=list)
    # New field
    session: Session | None = None   # Persistent session if loaded/created
```

---

## New Files to Create

```
src/persistence/__init__.py
```
Package init for the persistence layer.

```
src/persistence/session_store.py
```
`SessionStore` abstract base class defining the interface (`load`, `save`,
`list_sessions`, `delete`).

```
src/persistence/local_store.py
```
`LocalSessionStore` implementation. Stores sessions as JSON files in
`~/.house-hunt/sessions/{session_id}.json`. Creates the directory if absent.

```
src/persistence/h2c_quest_store.py
```
`H2CQuestStore` implementation. Reads/writes session data via H2C quest API.
Falls back gracefully when H2C is unreachable.

```
src/persistence/session_manager.py
```
High-level `SessionManager` that composes `LocalSessionStore` and optionally
`H2CQuestStore`. Implements the sync logic (local write first, then H2C sync).
Resolves conflicts with a "latest wins" strategy.

```
src/persistence/migrations.py
```
Schema version migration functions. Converts old session JSON to current schema.
Needed immediately because session files will persist across harness upgrades.

```
tests/persistence/test_local_store.py
```
Unit tests for local session file read/write/list/delete.

```
tests/persistence/test_session_manager.py
```
Tests for sync logic, conflict resolution, and H2C fallback behaviour.

---

## Changes to Existing Files

### `src/harness/orchestrator.py`
- Accept `session: Session | None` in `__init__`. If provided, pre-populate
  `self.state.session`.
- Add `shortlist_listing(listing_id: str, note: str | None = None)` method.
  Adds a `ShortlistEntry` to `self.state.session.shortlist` and saves the session.
- Add `reject_listing(listing_id: str, reason: str | None = None)` method.
  Sets `ShortlistEntry.status = "rejected"` and saves.
- Add `add_note(listing_id: str, text: str)` method. Appends a `ListingNote` and
  saves.
- Update `triage()` to append a `SearchRecord` to `self.state.session.search_history`.
- Update `create_comparison()` to store the comparison URL in the session and sync
  to the H2C quest.

### `src/ui/cli.py`
- Add `--resume [session_id]` argument. If `session_id` is omitted, auto-select
  the most recently modified session.
- Add `--new` argument to force a fresh session even if recent sessions exist.
- Add `--list-sessions` argument to print all saved sessions with their created_at
  and shortlist count.
- After listing display, prompt: "Shortlist this? [y/N]" with optional note.
- Add post-session summary: "Session saved. Resume later with: house-hunt --resume
  {session_id}"
- If H2C quest was created or updated, display quest URL.

### `src/harness/session_state.py`
- Add `session: Session | None = None` field.

### `src/app.py`
- Update `build_app()` to accept an optional `session: Session` parameter.
- Pass session to `HouseHuntOrchestrator.__init__`.

### `src/connectors/homestocompare_connector.py`
- Add `create_quest(session: Session) -> dict` method.
  POSTs to `/api/quests/create` with buyer profile and initial shortlist.
  Returns `{quest_id, quest_url}`.
- Add `sync_quest_shortlist(quest_id: str, shortlist: list[ShortlistEntry]) -> dict`
  method. PATCHes the quest shortlist.
- Add `get_quest(quest_id: str) -> dict` method. GETs `/mq/[quest_id]` data.

---

## MCP Server Tools

```python
@mcp.tool()
def save_session(
    brief: str,
    shortlisted_listings: list[dict],
    notes: dict[str, str] | None = None,
    session_id: str | None = None,
) -> dict:
    """Save or update a house-hunting session.

    Creates a new session (with a UUID) if session_id is omitted, or
    updates an existing session if session_id is provided.

    Args:
        brief: The buyer's raw search brief (used to rebuild the BuyerProfile).
        shortlisted_listings: Listing dicts the buyer wants to track.
        notes: Optional {listing_id: note_text} mapping.
        session_id: Existing session ID to update, or null to create new.

    Returns:
        {session_id, created_at, updated_at, shortlist_count,
         h2c_quest_url (if H2C is configured), local_path}
    """
    ...
```

```python
@mcp.tool()
def load_session(session_id: str | None = None) -> dict:
    """Load a saved session.

    If session_id is null, loads the most recently modified session.

    Returns the full session dict including buyer_profile, shortlist
    (with notes and status per listing), and search_history.
    Returns {status: "not_found"} if no session exists.
    """
    ...
```

```python
@mcp.tool()
def list_sessions() -> list[dict]:
    """List all saved sessions.

    Returns a list of session summaries, each with:
    session_id, created_at, updated_at, shortlist_count,
    last_brief (truncated), h2c_quest_url (if synced).

    Sorted most-recently-updated first.
    """
    ...
```

```python
@mcp.tool()
def shortlist_listing(
    session_id: str,
    listing: dict,
    note: str | None = None,
) -> dict:
    """Add a listing to the shortlist for a session.

    If the listing is already shortlisted, updates its note. If it was
    previously rejected, re-activates it.

    Returns: {session_id, shortlist_count, h2c_quest_synced: bool}
    """
    ...
```

```python
@mcp.tool()
def add_listing_note(
    session_id: str,
    listing_id: str,
    note_text: str,
) -> dict:
    """Add or update a note on a shortlisted listing.

    Notes are stored per listing within the session and synced to the
    H2C quest if one is linked.

    Returns: {session_id, listing_id, note_saved: true}
    """
    ...
```

---

## Implementation Phases

### Phase 1 — Local session file
**Deliverable:** `house-hunt --resume` works from a local JSON file.

- Implement `Session`, `ShortlistEntry`, `SearchRecord`, `ListingNote` dataclasses.
- Implement `LocalSessionStore` with `save`, `load`, `list_sessions`.
- Update CLI to accept `--resume [id]`, `--new`, `--list-sessions`.
- After each triage, append `SearchRecord`. After interactive listing display, prompt
  for shortlisting.
- Session file is written to `~/.house-hunt/sessions/{session_id}.json`.
- End of session: print resume command.

### Phase 2 — MCP session tools
**Deliverable:** Claude Code can manage sessions via MCP tools.

- Implement `save_session`, `load_session`, `list_sessions`, `shortlist_listing`,
  `add_listing_note` MCP tools.
- `SessionManager` class wiring `LocalSessionStore` into the tool layer.
- Unit tests for all five tools with mock store.

### Phase 3 — H2C quest creation and sync
**Deliverable:** Session is backed by an H2C quest; buyer has a shareable URL.

- Implement `create_quest`, `sync_quest_shortlist`, `get_quest` in
  `HomesToCompareConnector`.
- `H2CQuestStore` implementation. On save: write local first, then sync to H2C
  if `H2C_BASE_URL` and `H2C_HARNESS_KEY` are set.
- On `--resume`: merge local session with any H2C quest updates (merge strategy:
  keep all entries from both, latest note wins per listing).
- Display quest URL at end of session.

### Phase 4 — Session diffing and change alerts
**Deliverable:** Buyer sees what changed since last session.

- On resume, compare current listing prices and availability against the last
  `SearchRecord`. Surface: "Listing X price dropped by £5,000 since your last session",
  "Listing Y is no longer available".
- `src/skills/session_diff.py`: `diff_sessions(old: Session, new: Session) -> list[str]`.
- Display diff at the start of a resumed session before new search results.
- Add `session_diff` MCP tool.

---

## Testing Plan

### Unit tests

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_local_store_save_creates_file` | new `Session` object | JSON file created at `~/.house-hunt/sessions/{id}.json` |
| `test_local_store_load_roundtrip` | save then load same session_id | loaded `Session` equals saved `Session` |
| `test_local_store_list_sorted_by_updated` | three sessions with different `updated_at` | returned in descending updated_at order |
| `test_local_store_auto_creates_dir` | sessions dir does not exist | dir created, no error |
| `test_shortlist_adds_entry` | session with empty shortlist, call `shortlist_listing` | `session.shortlist` has one entry |
| `test_shortlist_updates_existing` | listing already shortlisted, add note | note updated, no duplicate entry |
| `test_shortlist_reactivates_rejected` | listing with status="rejected", shortlist again | status becomes "active" |
| `test_session_version_migration` | old session JSON with `version=1` | migrated to current schema, no data loss |
| `test_search_record_appended` | run triage twice in one session | `search_history` has two records |
| `test_resume_loads_profile` | session with `buyer_profile`, `--resume` | profile pre-populated, not re-asked |

### File system tests

```python
def test_session_file_is_valid_json(tmp_path):
    store = LocalSessionStore(sessions_dir=tmp_path)
    session = Session(session_id="test-123", ...)
    store.save(session)
    raw = (tmp_path / "test-123.json").read_text()
    parsed = json.loads(raw)
    assert parsed["session_id"] == "test-123"
    assert parsed["version"] == CURRENT_SCHEMA_VERSION
```

### Integration tests (require H2C credentials)

```bash
export H2C_BASE_URL=https://homestocompare.com
export H2C_HARNESS_KEY=<key>
uv run pytest tests/persistence/test_h2c_quest_store.py -m integration
# Expected: quest created, quest_url returned, shortlist synced
```

### CLI tests

```bash
# New session
uv run house-hunt search
# Type brief, shortlist 1 listing, exit
# Expected: "Session saved. Resume with: house-hunt --resume <id>"

# List sessions
uv run house-hunt --list-sessions
# Expected: shows the session just created

# Resume
uv run house-hunt --resume <id>
# Expected: profile pre-populated, asks to confirm or change, shows shortlisted listings
```

---

## Open Questions

1. **Session identity.** The session ID is a UUID. Should it also have a
   human-readable name (e.g. "london-search-april-2026") to make `--list-sessions`
   output readable? If so, should the harness auto-generate a name from the brief, or
   ask the buyer?

2. **Profile evolution.** A buyer's budget or requirements may change between sessions.
   If the buyer's brief on a resumed session differs from the saved profile, should
   the harness: (a) update the saved profile, (b) create a new session, or (c) ask?
   The right answer depends on whether "same search, different day" and "new search"
   should share a session.

3. **H2C quest creation trigger.** Should the quest be created on first run (even
   before any listings are shortlisted) or only when the buyer shortlists a listing?
   An empty quest is somewhat wasteful; a delayed creation means the buyer gets their
   shareable URL later.

4. **Conflict resolution on merge.** If the buyer added a note to a listing via the
   H2C website, and also added a different note locally, "latest wins" discards one
   note. Is this acceptable, or should notes be appended (keeping both with timestamps)?

5. **Session deletion.** The plan includes `SessionStore.delete()` but the CLI does
   not yet have a `--delete-session` command. Should deletion be possible, and if so,
   should it also delete the linked H2C quest, or just unlink it?

6. **Multi-buyer sessions.** Two buyers (a couple) may both be running the harness
   against the same quest. The H2C quest would be the shared view, but local session
   files would diverge. Is concurrent multi-user session editing in scope?

7. **Listing data freshness on resume.** The shortlist stores full `Listing` objects.
   On resume, should the harness re-fetch the listing from H2C to check for price
   changes, or trust the snapshot? Re-fetching is more useful but requires an H2C
   connection that may not be available.
