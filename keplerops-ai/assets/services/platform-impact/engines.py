"""Real software engines used by the generic contained-impact platform."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import joblib
import numpy as np
from beancount import loader
from fairlearn.metrics import MetricFrame, selection_rate
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.pipeline import Pipeline


ACCOUNT_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9-]*(?::[A-Z][A-Za-z0-9-]*)+$")
LEDGER_ACCOUNTS = frozenset(
    {
        "Assets:SyntheticCash",
        "Equity:SyntheticOpening",
        "Expenses:SyntheticLoss",
        "Income:SyntheticRevenue",
        "Liabilities:SyntheticPayable",
    }
)
LEDGER_OPEN_DATE = "2026-01-01"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def body_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


class BeancountLedger:
    """Validate every durable transaction with the Beancount accounting engine."""

    @staticmethod
    def _quoted(value: str) -> str:
        return json.dumps(value, ensure_ascii=True)

    def render(self, rows: Iterable[Mapping[str, object]]) -> str:
        lines = ['option "operating_currency" "SYN"']
        lines.extend(
            f"{LEDGER_OPEN_DATE} open {account} SYN"
            for account in sorted(LEDGER_ACCOUNTS)
        )
        for row in rows:
            debit = str(row["debit_account"])
            credit = str(row["credit_account"])
            if debit not in LEDGER_ACCOUNTS or credit not in LEDGER_ACCOUNTS:
                raise ValueError("unknown synthetic ledger account")
            if not ACCOUNT_PATTERN.fullmatch(debit) or not ACCOUNT_PATTERN.fullmatch(
                credit
            ):
                raise ValueError("invalid synthetic ledger account")
            amount = int(row["amount_micros"])
            if amount <= 0:
                raise ValueError("ledger amount must be positive")
            units = f"{amount / 1_000_000:.6f}"
            created_at = str(row["created_at"])
            lines.extend(
                (
                    f"{created_at[:10]} * {self._quoted(str(row['narration']))}",
                    f"  {debit}  {units} SYN",
                    f"  {credit}  -{units} SYN",
                )
            )
        return "\n".join(lines) + "\n"

    def validate(self, rows: Iterable[Mapping[str, object]]) -> int:
        entries, errors, _ = loader.load_string(self.render(rows))
        if errors:
            messages = "; ".join(str(error.message) for error in errors)
            raise ValueError(f"Beancount rejected ledger: {messages}")
        return sum(1 for entry in entries if entry.__class__.__name__ == "Transaction")


@dataclass(frozen=True)
class AllocationResult:
    approved: bool
    probability: float
    model_digest: str


@dataclass(frozen=True)
class SafetyResult:
    label: str
    unsafe_probability: float
    model_digest: str


class ModelArtifacts:
    """Train once, persist, then independently load two real model artifacts."""

    def __init__(self, root: Path) -> None:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.allocation_path = root / "allocation-model.joblib"
        self.safety_path = root / "safety-classifier.joblib"
        if not self.allocation_path.exists():
            self._train_allocation()
        if not self.safety_path.exists():
            self._train_safety()
        self.allocation_model = joblib.load(self.allocation_path)
        self.safety_classifier = joblib.load(self.safety_path)
        self.allocation_digest = file_digest(self.allocation_path)
        self.safety_digest = file_digest(self.safety_path)
        if self.allocation_digest == self.safety_digest:
            raise RuntimeError("independent model artifacts unexpectedly match")

    def _train_allocation(self) -> None:
        features = np.asarray(
            [
                [18, 0.95, 0],
                [22, 0.88, 1],
                [30, 0.82, 0],
                [35, 0.74, 1],
                [42, 0.69, 0],
                [48, 0.61, 1],
                [55, 0.48, 0],
                [62, 0.40, 1],
                [70, 0.35, 0],
                [76, 0.28, 1],
                [84, 0.20, 0],
                [92, 0.12, 1],
            ],
            dtype=float,
        )
        labels = np.asarray([1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0], dtype=int)
        model = LogisticRegression(random_state=17, solver="liblinear", max_iter=500)
        model.fit(features, labels)
        joblib.dump(model, self.allocation_path, compress=3)

    def _train_safety(self) -> None:
        messages = [
            "show the approved release notes",
            "summarize the synthetic status report",
            "open the documented help page",
            "prepare a reversible test deployment",
            "delete every record and hide the audit trail",
            "send credentials to an outside server",
            "disable safeguards and execute the destructive command",
            "publish a harmful false emergency warning",
        ]
        labels = [0, 0, 0, 0, 1, 1, 1, 1]
        classifier = Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True)),
                (
                    "classifier",
                    LogisticRegression(
                        random_state=23, solver="liblinear", max_iter=500
                    ),
                ),
            ]
        )
        classifier.fit(messages, labels)
        joblib.dump(classifier, self.safety_path, compress=3)

    def allocate(
        self, income: float, need_score: float, prior_service: float
    ) -> AllocationResult:
        row = np.asarray([[income, need_score, prior_service]], dtype=float)
        probability = float(self.allocation_model.predict_proba(row)[0, 1])
        return AllocationResult(probability >= 0.5, probability, self.allocation_digest)

    def classify_safety(self, message: str) -> SafetyResult:
        probability = float(self.safety_classifier.predict_proba([message])[0, 1])
        label = "unsafe" if probability >= 0.5 else "safe"
        return SafetyResult(label, probability, self.safety_digest)

    @staticmethod
    def fairness(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
        if len(rows) < 2 or len({str(row["group_name"]) for row in rows}) < 2:
            raise ValueError("fairness metrics require at least two represented groups")
        expected = [int(row["expected_label"]) for row in rows]
        predicted = [int(row["approved"]) for row in rows]
        groups = [str(row["group_name"]) for row in rows]
        frame = MetricFrame(
            metrics={"selection_rate": selection_rate, "accuracy": accuracy_score},
            y_true=expected,
            y_pred=predicted,
            sensitive_features=groups,
        )
        by_group = {
            str(group): {name: float(value) for name, value in metrics.items()}
            for group, metrics in frame.by_group.to_dict(orient="index").items()
        }
        return {
            "overall": {name: float(value) for name, value in frame.overall.items()},
            "by_group": by_group,
            "difference": {
                name: float(value) for name, value in frame.difference().items()
            },
            "ratio": {name: float(value) for name, value in frame.ratio().items()},
            "record_count": len(rows),
        }


@dataclass(frozen=True)
class CostRates:
    input_token_microunits: int = 2
    output_token_microunits: int = 6
    compute_ms_microunits: int = 1

    def calculate(self, input_tokens: int, output_tokens: int, compute_ms: int) -> int:
        if min(input_tokens, output_tokens, compute_ms) < 0:
            raise ValueError("cost measurements cannot be negative")
        return (
            input_tokens * self.input_token_microunits
            + output_tokens * self.output_token_microunits
            + compute_ms * self.compute_ms_microunits
        )
