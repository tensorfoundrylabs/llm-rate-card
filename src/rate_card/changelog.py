from dataclasses import dataclass, field

_PRICE_FIELDS = frozenset(
    {
        "input_per_million",
        "output_per_million",
        "cache_read_per_million",
        "cache_write_per_million",
        "reasoning_per_million",
    }
)

_NON_PRICE_FIELDS = frozenset(
    {
        "capabilities",
        "context_window",
        "max_output_tokens",
        "deprecation_date",
        "mode",
        "source_url",
    }
)

_Entry = dict[str, object]


@dataclass
class ChangeSummary:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    repriced: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)


def _tiers_differ(prev: list[_Entry], curr: list[_Entry]) -> bool:
    if len(prev) != len(curr):
        return True
    for p, c in zip(prev, curr, strict=True):
        for price_field in (
            "input_per_million",
            "output_per_million",
            "cache_read_per_million",
            "cache_write_per_million",
        ):
            if p.get(price_field) != c.get(price_field):
                return True
    return False


def _is_repriced(prev: _Entry, curr: _Entry) -> bool:
    if any(prev.get(f) != curr.get(f) for f in _PRICE_FIELDS):
        return True
    prev_tiers: list[_Entry] = prev.get("pricing_tiers") or []  # type: ignore[assignment]
    curr_tiers: list[_Entry] = curr.get("pricing_tiers") or []  # type: ignore[assignment]
    return _tiers_differ(prev_tiers, curr_tiers)


def _is_updated(prev: _Entry, curr: _Entry) -> bool:
    return any(prev.get(f) != curr.get(f) for f in _NON_PRICE_FIELDS)


def summarise(previous: dict[str, object] | None, current: dict[str, object]) -> ChangeSummary:
    """Compute a structured diff between two rate-card documents."""
    summary = ChangeSummary()
    raw_curr: list[_Entry] = current.get("models") or []  # type: ignore[assignment]
    curr_models: dict[str, _Entry] = {str(m["key"]): m for m in raw_curr}

    if previous is None or not previous.get("models"):
        summary.added = sorted(curr_models)
        return summary

    raw_prev: list[_Entry] = previous.get("models") or []  # type: ignore[assignment]
    prev_models: dict[str, _Entry] = {str(m["key"]): m for m in raw_prev}

    for key in sorted(curr_models):
        if key not in prev_models:
            summary.added.append(key)

    for key in sorted(prev_models):
        if key not in curr_models:
            summary.removed.append(key)

    for key in sorted(set(prev_models) & set(curr_models)):
        prev_entry = prev_models[key]
        curr_entry = curr_models[key]
        if _is_repriced(prev_entry, curr_entry):
            summary.repriced.append(key)
        elif _is_updated(prev_entry, curr_entry):
            summary.updated.append(key)

    return summary


def format_summary(summary: ChangeSummary) -> str:
    """Return a markdown block summarising the change categories."""
    parts: list[str] = []

    counts: list[str] = []
    if summary.added:
        counts.append(f"{len(summary.added)} added")
    if summary.removed:
        counts.append(f"{len(summary.removed)} removed")
    if summary.repriced:
        counts.append(f"{len(summary.repriced)} repriced")
    if summary.updated:
        counts.append(f"{len(summary.updated)} updated")

    if not counts:
        return "No changes."

    parts.append(f"**Changes**: {', '.join(counts)}")

    if summary.added:
        parts.append("")
        parts.append("Added:")
        for key in summary.added:
            parts.append(f"- `{key}`")

    if summary.removed:
        if summary.added:
            parts.append("")
        parts.append("Removed:")
        for key in summary.removed:
            parts.append(f"- `{key}`")

    return "\n".join(parts)


def format_release_notes(repo: str, previous_tag: str, current_tag: str) -> str:
    """Return a one-line markdown string with a GitHub compare URL."""
    url = f"https://github.com/{repo}/compare/{previous_tag}...{current_tag}"
    return f"Changes since [{previous_tag}]({url})"
