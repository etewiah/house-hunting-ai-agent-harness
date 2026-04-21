# 04 - Persistent Sessions

## Purpose

House hunting is iterative. Buyers revisit listings, update priorities, add notes, share
shortlists, and compare new options against old ones. The harness should preserve this
work across runs without requiring a particular website or backend.

This feature defines a portable session model with optional sync adapters. Local JSON can
be the default; platforms such as HomesToCompare can provide richer shared persistence
when configured.

## Harness Contract

A session should store:

- Buyer profile and original briefs.
- Ranked listings or shortlist snapshots.
- Listing status: active, rejected, viewing booked, offer made, archived.
- Buyer notes and timestamps.
- Search history.
- Generated outputs: comparisons, affordability estimates, questions, exports.
- Optional external IDs and URLs from sync providers.
- Schema version for migrations.

The harness should support:

- Create a new session.
- Resume a recent or named session.
- List sessions.
- Add or update shortlist entries.
- Add notes.
- Track changes between snapshots when fresh listing data is available.

## LLM Responsibilities

The LLM should:

- Use session history to avoid repeating work.
- Respect explicit buyer decisions such as rejected listings.
- Distinguish old snapshot data from fresh data.
- Ask before merging materially different buyer briefs into the same session.
- Explain conflicts when local and remote state differ.

The LLM should not assume that a platform account or internet connection is available.

## Suggested Data Shape

```python
@dataclass
class ListingNote:
    listing_id: str
    text: str
    created_at: str
    updated_at: str
    source: str


@dataclass
class ShortlistEntry:
    listing: Listing
    added_at: str
    status: str
    notes: list[ListingNote] = field(default_factory=list)
    ranked_score: float | None = None


@dataclass
class Session:
    session_id: str
    created_at: str
    updated_at: str
    buyer_profile: BuyerProfile | None
    shortlist: list[ShortlistEntry]
    search_history: list[dict]
    generated_outputs: dict = field(default_factory=dict)
    external_refs: dict = field(default_factory=dict)
    version: int = 1
```

`external_refs` can hold platform-specific IDs without forcing the core session schema to
know about one provider.

## Storage Adapter Pattern

```python
class SessionStore(Protocol):
    def load(self, session_id: str) -> Session | None: ...
    def save(self, session: Session) -> Session: ...
    def list_sessions(self) -> list[Session]: ...
    def delete(self, session_id: str) -> bool: ...
```

Recommended adapters:

- Local JSON store for the default path.
- Optional platform store for shared web access.
- Optional SQLite store if local querying becomes important.

Sync behavior should be explicit and conservative. Local-first save with later remote sync
is a good default.

## Platform Integration

A platform integration can map a session to a quest, project, collection, saved search, or
folder. The harness should only require:

- Create or link an external container.
- Sync shortlist and notes.
- Read remote changes on resume.
- Store returned URLs in `external_refs`.

HomesToCompare quests are one possible implementation, not a core assumption.

## Implementation Guidance

- Add migrations as soon as session files can persist between releases.
- Store listing snapshots, but mark them as snapshots.
- Re-fetch live listing data on resume only when a connector is configured.
- Merge notes by timestamp where possible; avoid discarding user text.
- Provide clear CLI and MCP tools for create, resume, list, shortlist, and note actions.

## Testing Focus

- Sessions round-trip through the default local store.
- Listing notes and statuses survive resume.
- Missing or corrupt session files fail gracefully.
- Schema migrations preserve existing data.
- Remote sync failure does not lose local changes.

## Open Questions

- Should sessions have human-readable names?
- When a buyer changes their brief, should the harness update the session or create a new one?
- Should deletion remove only local state or also remote synced state?
