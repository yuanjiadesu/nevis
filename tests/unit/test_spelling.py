from nevis.application.spelling import correct_final_token


class _Dictionary:
    def __init__(self, candidates: set[str], frequencies: dict[str, float]) -> None:
        self._candidates = candidates
        self._frequencies = frequencies

    def unknown(self, words: list[str]) -> set[str]:
        return set(words)

    def candidates(self, word: str) -> set[str] | None:
        return self._candidates

    def word_usage_frequency(self, word: str) -> float:
        return self._frequencies[word]


def test_corrects_one_eligible_final_token() -> None:
    assert correct_final_token("investment opportunit") == "investment opportunity"


def test_does_not_correct_known_short_or_non_alphabetic_final_tokens() -> None:
    assert correct_final_token("green investing") is None
    assert correct_final_token("green teh") is None
    assert correct_final_token("green opportunit1") is None


def test_rejects_tied_dictionary_candidates() -> None:
    dictionary = _Dictionary({"chance", "change"}, {"chance": 0.5, "change": 0.5})

    assert correct_final_token("future chnce", dictionary=dictionary) is None


def test_uses_unique_highest_frequency_candidate() -> None:
    dictionary = _Dictionary(
        {"opportunist", "opportunity"},
        {"opportunist": 0.1, "opportunity": 0.9},
    )

    assert (
        correct_final_token("investment opportunit", dictionary=dictionary)
        == "investment opportunity"
    )
