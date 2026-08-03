from __future__ import annotations


def score_batch(inputs: list[str]) -> list[dict[str, object]]:
    return [
        {
            "input": value,
            "token_count": len(value.split()),
            "review_score": round(min(1.0, len(value.split()) / 12.0), 6),
        }
        for value in inputs
    ]
