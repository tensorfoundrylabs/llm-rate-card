def format_release_notes(repo: str, previous_tag: str, current_tag: str) -> str:
    """Return a one-line markdown string with a GitHub compare URL."""
    url = f"https://github.com/{repo}/compare/{previous_tag}...{current_tag}"
    return f"Changes since [{previous_tag}]({url})"
