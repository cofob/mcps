from collections.abc import Sequence


def truncation_suffix(shown: int, total: int) -> str:
    if shown >= total:
        return ""
    return f" Showing {shown} of {total}."


def bullet_list(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items)
