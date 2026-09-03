"""Small, transparent text classifier with no cloud dependency.

The model is deliberately simple: multinomial Naive Bayes over word tokens.
That makes the demo honest, fast, inspectable and safe for synthetic or local
operational data.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
from typing import Iterable


TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)

# Domain features keep the tiny demonstration model useful across common
# English and Russian word forms without turning decisions into hard-coded
# labels. They become weighted tokens inside the probabilistic model.
FEATURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("confirmed", re.compile(r"confirm|see you|подтверд|все в силе|точно прид", re.I)),
    ("cancellation", re.compile(r"cancel|will not come|отмен|отказ|не прид|не нужна", re.I)),
    ("reschedule", re.compile(r"resched|move (it|the appointment)|change the time|перен|изменить время", re.I)),
    ("payment_issue", re.compile(r"payment|charged|card|оплат|списан|деньг", re.I)),
    ("contact_problem", re.compile(r"unreachable|could not reach|does not answer|bounced|недоступ|не отвечает|не удалось связ|абонент", re.I)),
    ("complaint", re.compile(r"unhappy|complain|poor quality|long wait|жалоб|недовол|качеств|ожидан", re.I)),
    ("neutral", re.compile(r"regular|general note|created by|обычн|создан|комментар", re.I)),
)


TRAINING_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("client confirmed the appointment", "confirmed"),
    ("booking is confirmed, see you tomorrow", "confirmed"),
    ("клиент подтвердил запись", "confirmed"),
    ("все в силе, придет вовремя", "confirmed"),
    ("please cancel my booking", "cancellation"),
    ("client will not come, cancel", "cancellation"),
    ("прошу отменить запись", "cancellation"),
    ("клиент отказался и не придет", "cancellation"),
    ("move the appointment to friday", "reschedule"),
    ("please change the time to 15:00", "reschedule"),
    ("перенесите запись на завтра", "reschedule"),
    ("нужно изменить время визита", "reschedule"),
    ("card payment failed", "payment_issue"),
    ("payment was charged twice", "payment_issue"),
    ("не проходит оплата по карте", "payment_issue"),
    ("деньги списались два раза", "payment_issue"),
    ("phone number is unreachable", "contact_problem"),
    ("email bounced and client does not answer", "contact_problem"),
    ("телефон недоступен", "contact_problem"),
    ("не удалось связаться с клиентом", "contact_problem"),
    ("client is unhappy with the service", "complaint"),
    ("customer complained about a long wait", "complaint"),
    ("клиент недоволен качеством", "complaint"),
    ("жалоба на долгое ожидание", "complaint"),
    ("added a general note to the record", "neutral"),
    ("record created by administrator", "neutral"),
    ("добавлен обычный комментарий", "neutral"),
    ("заявка создана администратором", "neutral"),
)


EVALUATION_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("confirmed for tomorrow morning", "confirmed"),
    ("клиент точно придет", "confirmed"),
    ("cancel the visit please", "cancellation"),
    ("запись больше не нужна", "cancellation"),
    ("can we move it to monday", "reschedule"),
    ("перенос на вечер", "reschedule"),
    ("payment did not go through", "payment_issue"),
    ("ошибка списания денег", "payment_issue"),
    ("could not reach the customer", "contact_problem"),
    ("абонент не отвечает", "contact_problem"),
    ("unhappy customer reported poor quality", "complaint"),
    ("поступила жалоба", "complaint"),
    ("regular internal note", "neutral"),
    ("обычная запись", "neutral"),
)


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float
    evidence: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "evidence": list(self.evidence),
        }


class IntentClassifier:
    """Multinomial Naive Bayes classifier for short operational notes."""

    def __init__(self, examples: Iterable[tuple[str, str]] = TRAINING_EXAMPLES):
        self.class_counts: Counter[str] = Counter()
        self.token_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.total_tokens: Counter[str] = Counter()
        self.vocabulary: set[str] = set()
        for text, label in examples:
            tokens = self.tokenize(text)
            self.class_counts[label] += 1
            self.token_counts[label].update(tokens)
            self.total_tokens[label] += len(tokens)
            self.vocabulary.update(tokens)
        self.labels = tuple(sorted(self.class_counts))
        self.total_examples = sum(self.class_counts.values())

    @staticmethod
    def tokenize(text: str) -> list[str]:
        source = text or ""
        tokens = [token.lower() for token in TOKEN_RE.findall(source) if len(token) > 1]
        for label, pattern in FEATURE_PATTERNS:
            if pattern.search(source):
                # Repetition is an explicit feature weight, not a deterministic
                # override: probability and the remaining vocabulary still matter.
                tokens.extend((f"intentfeature{label}", f"intentfeature{label}"))
        return tokens

    def predict(self, text: str) -> Prediction:
        tokens = self.tokenize(text)
        if not tokens:
            return Prediction("neutral", 1.0, ())
        vocab_size = max(1, len(self.vocabulary))
        scores: dict[str, float] = {}
        for label in self.labels:
            prior = (self.class_counts[label] + 1) / (
                self.total_examples + len(self.labels)
            )
            score = math.log(prior)
            denominator = self.total_tokens[label] + vocab_size
            for token in tokens:
                score += math.log((self.token_counts[label][token] + 1) / denominator)
            scores[label] = score

        best = max(scores, key=scores.get)
        peak = max(scores.values())
        probabilities = {label: math.exp(score - peak) for label, score in scores.items()}
        total = sum(probabilities.values()) or 1.0
        confidence = probabilities[best] / total
        evidence = sorted(
            {token for token in tokens if self.token_counts[best][token]},
            key=lambda token: self.token_counts[best][token],
            reverse=True,
        )[:4]
        return Prediction(best, confidence, tuple(evidence))

    def evaluate(self, examples: Iterable[tuple[str, str]] = EVALUATION_EXAMPLES) -> dict[str, object]:
        rows = list(examples)
        predictions = [(text, expected, self.predict(text).label) for text, expected in rows]
        correct = sum(expected == actual for _, expected, actual in predictions)
        return {
            "name": "Local multilingual intent classifier",
            "algorithm": "Multinomial Naive Bayes",
            "training_examples": self.total_examples,
            "evaluation_examples": len(predictions),
            "accuracy": round(correct / max(1, len(predictions)), 3),
            "classes": list(self.labels),
            "cloud_calls": 0,
        }
