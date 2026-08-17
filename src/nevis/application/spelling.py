from functools import lru_cache
from typing import Protocol

from spellchecker import SpellChecker


class SpellDictionary(Protocol):
    def unknown(self, words: list[str]) -> set[str]: ...

    def candidates(self, word: str) -> set[str] | None: ...

    def word_usage_frequency(self, word: str) -> float: ...


@lru_cache(maxsize=1)
def _english_dictionary() -> SpellChecker:
    return SpellChecker(language="en", distance=1)


def correct_final_token(query: str, *, dictionary: SpellDictionary | None = None) -> str | None:
    """Return one conservative dictionary correction without retaining query text."""
    prefix, separator, token = query.rpartition(" ")
    if not token.isalpha() or len(token) < 5:
        return None

    normalized = token.casefold()
    words = dictionary or _english_dictionary()
    if not words.unknown([normalized]):
        return None

    candidates = words.candidates(normalized) or set()
    if not candidates:
        return None
    frequencies = {candidate: words.word_usage_frequency(candidate) for candidate in candidates}
    highest = max(frequencies.values())
    winners = sorted(
        candidate for candidate, frequency in frequencies.items() if frequency == highest
    )
    if len(winners) != 1 or winners[0] == normalized:
        return None

    corrected = winners[0]
    return f"{prefix}{separator}{corrected}" if separator else corrected
