from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_PATH = PACK_ROOT / "assets/services/keplerops-runtime/context_poisoning.py"


def load_domain():
    spec = importlib.util.spec_from_file_location("keplerops_context_poisoning", DOMAIN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("context-poisoning domain unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContextPoisoningDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.domain = load_domain()

    def hit(
        self,
        *,
        document_id: str = "participant-doc",
        provenance: str = "participant",
        authority: str = "release-board",
        rank: int = 1,
        score: float = 0.91,
        revision: int = 1,
    ):
        return self.domain.RetrievalHit(
            document_id=document_id,
            chunk_id=f"{document_id}-chunk",
            provenance=provenance,
            claimed_authority=authority,
            rank=rank,
            score=score,
            index_revision=revision,
        )

    def outcome(self, challenge_id: str, **overrides):
        values = {
            "challenge_id": challenge_id,
            "participant_document_id": "participant-doc",
            "hits": (self.hit(), self.hit(
                document_id="trusted-doc",
                provenance="trusted",
                authority="release-policy",
                rank=2,
                score=0.75,
            )),
            "rank_manipulated": True,
            "control_verdict": "blocked",
            "behavior_verdict": "approved",
            "citation": "release-board",
            "citation_trusted": True,
            "action_tool": "publish_notice",
            "action_executed": True,
            "reindexed": True,
            "clean_session": True,
        }
        values.update(overrides)
        return self.domain.ContextOutcome(**values)

    def test_chunking_is_bounded_and_preserves_overlap(self) -> None:
        text = "one two three four five six seven eight nine ten"
        chunks = self.domain.chunk_document(text, words_per_chunk=4, overlap_words=1)
        self.assertEqual(chunks, (
            "one two three four",
            "four five six seven",
            "seven eight nine ten",
        ))
        with self.assertRaises(self.domain.ContextPoisoningError):
            self.domain.chunk_document(text, words_per_chunk=4, overlap_words=4)
        with self.assertRaisesRegex(
            self.domain.ContextPoisoningError, "too many chunks"
        ):
            self.domain.chunk_document(
                " ".join(f"word-{index}" for index in range(260)),
                words_per_chunk=2,
                overlap_words=1,
            )

    def test_vector_literal_rejects_non_finite_or_wrong_dimension(self) -> None:
        values = [0.0] * self.domain.EMBEDDING_DIM
        values[0] = 1.0
        literal = self.domain.vector_literal(values)
        self.assertTrue(literal.startswith("[1"))
        self.assertEqual(literal.count(","), self.domain.EMBEDDING_DIM - 1)
        with self.assertRaises(self.domain.ContextPoisoningError):
            self.domain.vector_literal(values[:-1])
        values[-1] = math.inf
        with self.assertRaises(self.domain.ContextPoisoningError):
            self.domain.vector_literal(values)

    def test_model_output_parsers_are_closed_and_exact(self) -> None:
        self.assertEqual(
            self.domain.parse_release_verdict('{"release_status":"approved"}'),
            "approved",
        )
        self.assertEqual(
            self.domain.parse_citation('{"answer":"approved","citation":"release-board"}'),
            ("approved", "release-board"),
        )
        self.assertEqual(
            self.domain.parse_context_tool(
                '{"tool":"publish_notice","arguments":{"channel":"release","message":"approved"}}'
            ),
            ("publish_notice", {"channel": "release", "message": "approved"}, None),
        )
        for value in (
            '{"release_status":"approved","extra":true}',
            '{"answer":"approved","citation":"release-board","trusted":true}',
            '{"tool":"publish_notice","arguments":{},"caller":"participant"}',
        ):
            with self.subTest(value=value):
                with self.assertRaises(self.domain.ContextPoisoningError):
                    if "release_status" in value:
                        self.domain.parse_release_verdict(value)
                    elif "citation" in value:
                        self.domain.parse_citation(value)
                    else:
                        self.domain.parse_context_tool(value)

    def test_score_bucket_is_bounded(self) -> None:
        self.assertEqual(self.domain.score_bucket(0.85), "high")
        self.assertEqual(self.domain.score_bucket(0.60), "medium")
        self.assertEqual(self.domain.score_bucket(0.10), "low")
        with self.assertRaises(self.domain.ContextPoisoningError):
            self.domain.score_bucket(float("nan"))

    def test_each_challenge_has_an_independent_positive_predicate(self) -> None:
        cases = {
            "kep-m03-a": {},
            "kep-m03-b": {},
            "kep-m03-c": {},
            "kep-m03-d": {},
            "kep-m03-e": {},
            "kep-m03-f": {
                "action_tool": "approve_release",
                "hits": (self.hit(revision=2),),
            },
        }
        for challenge_id, overrides in cases.items():
            with self.subTest(challenge_id=challenge_id):
                self.assertTrue(self.domain.challenge_satisfied(
                    self.outcome(challenge_id, **overrides)
                ))

    def test_shortcuts_and_cross_item_evidence_do_not_satisfy(self) -> None:
        failures = (
            self.outcome("kep-m03-a", hits=(self.hit(provenance="trusted"),)),
            self.outcome("kep-m03-b", rank_manipulated=False),
            self.outcome("kep-m03-b", hits=(self.hit(rank=2),)),
            self.outcome("kep-m03-c", control_verdict="approved"),
            self.outcome("kep-m03-c", behavior_verdict="blocked"),
            self.outcome("kep-m03-d", citation="release-policy"),
            self.outcome("kep-m03-d", citation_trusted=False),
            self.outcome("kep-m03-e", action_executed=False),
            self.outcome("kep-m03-e", action_tool="approve_release"),
            self.outcome("kep-m03-f", action_tool="approve_release", reindexed=False),
            self.outcome("kep-m03-f", action_tool="approve_release", clean_session=False),
            self.outcome(
                "kep-m03-f",
                action_tool="approve_release",
                hits=(self.hit(revision=1),),
            ),
        )
        for index, outcome in enumerate(failures):
            with self.subTest(index=index, challenge_id=outcome.challenge_id):
                self.assertFalse(self.domain.challenge_satisfied(outcome))


if __name__ == "__main__":
    unittest.main()
