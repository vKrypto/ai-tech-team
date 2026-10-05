ORDER = ["plan", "search", "analyze", "synthesize"]


def next_of(node: str, exit_to: str) -> str:
    i = ORDER.index(node)
    return ORDER[i + 1] if i + 1 < len(ORDER) else exit_to
