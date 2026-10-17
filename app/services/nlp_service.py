"""Natural-language understanding service for QuoteMate.

Provides:
1. Intent classification via TF-IDF + LogisticRegression.
2. Fuzzy product retrieval via RapidFuzz against SQLite catalogue products.
3. Quantity extraction supporting digits and written number words.
4. Structured NLP result generation without hallucinating items or quantities.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ProductModel
from app.schemas import MatchedProductItem, NLPAnalysisResult

DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "sample_data" / "messages_dataset.json"

WORD_TO_NUMBER: Dict[str, int] = {
    "zero": 0,
    "one": 1,
    "single": 1,
    "two": 2,
    "couple": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "dozen": 12,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "hundred": 100,
}

# Words to ignore when matching product names against clauses
PROMPT_FLUFF = {
    "please", "quote", "for", "i", "need", "want", "can", "you", "send", "give",
    "me", "buy", "calculate", "a", "an", "the", "some", "order", "units", "get", "to",
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
}

# Irregular English plurals that must map back to the catalogue noun form
IRREGULAR_PLURALS: Dict[str, str] = {
    "mice": "mouse",
}


def normalize_match_token(token: str) -> str:
    """Reduce a token to its base form for overlap comparisons.

    Handles irregular plurals (mice -> mouse) and simple trailing-'s'
    stripping (keyboards -> keyboard, hubs -> hub).
    """
    if token in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[token]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def extract_content_tokens(text: str) -> List[str]:
    """Return normalized content tokens with conversational fluff and digits removed."""
    raw_tokens = [
        w
        for w in re.findall(r"\b[a-z0-9-]+\b", text.lower())
        if w not in PROMPT_FLUFF and not w.isdigit()
    ]
    return [normalize_match_token(t) for t in raw_tokens]


def tokens_match(a: str, b: str) -> bool:
    """Return True when two normalized tokens refer to the same word.

    Exact equality always matches. Prefix matching (minimum length 3)
    tolerates common abbreviations such as 'mic' -> 'microphone' and
    'usb' -> 'usb-c' without allowing very short tokens to match
    unrelated words.
    """
    if a == b:
        return True
    if len(a) >= 3 and b.startswith(a):
        return True
    if len(b) >= 3 and a.startswith(b):
        return True
    return False


def has_meaningful_product_overlap(clause: str, product_name: str) -> bool:
    """Decide whether a clause shares meaningful content with a product name.

    A high RapidFuzz score alone is not sufficient evidence of a match:
    generic adjectives shared across categories (e.g. 'wireless' in both
    'Compact Wireless Keyboard' and 'Wireless Optical Mouse') can inflate
    token_set_ratio enough to cross the strong-match threshold for the
    wrong product. The clause must additionally share either:

    - the product name's head noun (its final content token, e.g.
      'keyboard', 'mouse', 'monitor'), or
    - at least two content tokens with the product name.
    """
    clause_tokens = extract_content_tokens(clause)
    name_tokens = extract_content_tokens(product_name)
    if not clause_tokens or not name_tokens:
        return False
    shared = {
        name_token
        for name_token in name_tokens
        if any(tokens_match(ct, name_token) for ct in clause_tokens)
    }
    if not shared:
        return False
    head_token = name_tokens[-1]
    return head_token in shared or len(shared) >= 2

# RapidFuzz match score thresholds
STRONG_MATCH_THRESHOLD = 68.0
AMBIGUOUS_MATCH_THRESHOLD = 52.0

# Minimum intent classification probability threshold (with 6 classes, uniform random is 0.1667)
INTENT_CONFIDENCE_THRESHOLD = 0.28


class NLPService:
    """Natural Language Processing service for WhatsApp sales enquiries."""

    def __init__(self, dataset_path: Optional[Path | str] = None):
        self.dataset_path = Path(dataset_path) if dataset_path else DATASET_PATH
        # Note: We do NOT remove standard English stopwords because short conversational messages
        # rely heavily on question words ('do', 'what', 'can'), polarity ('yes', 'no'), and pronouns.
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            lowercase=True,
            sublinear_tf=True,
        )
        self.classifier = LogisticRegression(
            C=5.0,
            random_state=42,
            max_iter=300,
        )
        self._is_trained = False
        self._train_size = 0
        self._eval_size = 0
        self._train_classifier()

    def _train_classifier(self) -> None:
        """Load training data from JSON and fit the vectorizer and classifier."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"NLP training dataset not found at: {self.dataset_path}")

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        training_samples = data.get("training", [])
        if not training_samples:
            raise ValueError("Training dataset contains no examples.")

        X_train = [s["text"] for s in training_samples]
        y_train = [s["intent"] for s in training_samples]

        X_vec = self.vectorizer.fit_transform(X_train)
        self.classifier.fit(X_vec, y_train)
        self._is_trained = True
        self._train_size = len(training_samples)
        self._eval_size = len(data.get("evaluation", []))

    def evaluate(self) -> Dict[str, object]:
        """Evaluate classifier on held-out evaluation examples and return metrics.

        Returns:
            Dict containing train size, test size, accuracy, and classification report dict.
        """
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        eval_samples = data.get("evaluation", [])
        if not eval_samples:
            raise ValueError("Evaluation dataset is empty.")

        X_test = [s["text"] for s in eval_samples]
        y_test = [s["intent"] for s in eval_samples]

        X_test_vec = self.vectorizer.transform(X_test)
        predictions = self.classifier.predict(X_test_vec)

        report = classification_report(y_test, predictions, output_dict=True, zero_division=0)
        return {
            "train_size": self._train_size,
            "evaluation_size": len(eval_samples),
            "accuracy": round(float(report["accuracy"]), 4),
            "classification_report": report,
        }

    def predict_intent(self, text: str) -> Tuple[str, float]:
        """Predict intent and confidence probability for given input text.

        Args:
            text: Customer message.

        Returns:
            Tuple of (predicted_intent, confidence_score).
        """
        cleaned_text = text.strip() if text else ""
        if not cleaned_text:
            return "unsupported", 0.0

        vec = self.vectorizer.transform([cleaned_text])
        probabilities = self.classifier.predict_proba(vec)[0]
        max_idx = probabilities.argmax()
        confidence = float(probabilities[max_idx])
        predicted_class = self.classifier.classes_[max_idx]

        # Apply conservative fallback if confidence is near random chance
        if confidence < INTENT_CONFIDENCE_THRESHOLD:
            return "unsupported", round(confidence, 4)

        return str(predicted_class), round(confidence, 4)

    def extract_quantity_from_phrase(self, phrase: str) -> Tuple[Optional[int], bool, bool]:
        """Extract quantity from phrase.

        Returns:
            Tuple[quantity, has_zero_or_negative, has_quantity]
        """
        lower = phrase.lower()

        # Look for negative digits: e.g. "-2" or "-5"
        if re.search(r"-\s*\d+", lower):
            return None, True, True

        # Look for zero digits: e.g. "0"
        if re.search(r"\b0\b", lower):
            return 0, True, True

        # Look for word-based zero
        if re.search(r"\bzero\b", lower):
            return 0, True, True

        # Check for digits first (e.g. "3 keyboards", "10 units")
        digit_matches = re.findall(r"\b\d+\b", lower)
        if digit_matches:
            val = int(digit_matches[0])
            if val <= 0:
                return val, True, True
            return val, False, True

        # Check for number words
        tokens = re.findall(r"\b[a-z]+\b", lower)
        for token in tokens:
            if token in WORD_TO_NUMBER:
                val = WORD_TO_NUMBER[token]
                if val <= 0:
                    return val, True, True
                return val, False, True

        # No quantity found
        return None, False, False

    def match_products(
        self, text: str, db: Optional[Session] = None
    ) -> List[MatchedProductItem]:
        """Match catalogue products from the SQLite database using RapidFuzz.

        Args:
            text: Customer message text.
            db: Optional database session. If omitted, uses temporary session.

        Returns:
            List of matched products with quantities and confidence scores.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            # Query actual database catalogue
            products: List[ProductModel] = session.scalars(select(ProductModel)).all()
            if not products:
                return []

            matched_items: List[MatchedProductItem] = []
            lower_text = text.lower()

            # Split message into candidate clauses by punctuation or conjunctions
            clauses = [
                c.strip()
                for c in re.split(r"[,;.!?]|\band\b|\balso\b", lower_text)
                if c.strip()
            ]
            if not clauses:
                clauses = [lower_text]

            matched_product_ids = set()

            for product in products:
                prod_name_lower = product.name.lower()
                best_score = 0.0
                best_clause = ""

                # Evaluate match against each clause (raw and with conversational fluff stripped)
                for clause in clauses:
                    tokens = [
                        w for w in re.findall(r"\b[a-z0-9-]+\b", clause)
                        if w not in PROMPT_FLUFF and not w.isdigit()
                    ]
                    clean_clause = " ".join(tokens)
                    raw_score = fuzz.token_set_ratio(clause, prod_name_lower)
                    clean_score = (
                        fuzz.token_set_ratio(clean_clause, prod_name_lower)
                        if clean_clause
                        else 0.0
                    )
                    score = max(raw_score, clean_score)
                    if score > best_score:
                        best_score = score
                        best_clause = clause

                # Only evaluate full text partial match if single clause
                if len(clauses) == 1:
                    full_score = fuzz.partial_ratio(lower_text, prod_name_lower)
                    if full_score > best_score:
                        best_score = max(best_score, full_score)
                        best_clause = lower_text

                # Guard: a candidate must share meaningful content tokens with
                # the clause. A generic word such as 'wireless' that appears in
                # many catalogue names cannot independently justify a match;
                # the clause must match the product's head noun (e.g.
                # 'mouse', 'keyboard') or at least two of its name tokens.
                if not has_meaningful_product_overlap(best_clause, prod_name_lower):
                    continue

                # Evaluate against strong and ambiguous thresholds
                if best_score >= STRONG_MATCH_THRESHOLD:
                    if product.id not in matched_product_ids:
                        qty, is_invalid, has_qty = self.extract_quantity_from_phrase(best_clause)
                        if not has_qty and len(clauses) == 1:
                            qty, is_invalid, has_qty = self.extract_quantity_from_phrase(lower_text)

                        matched_items.append(
                            MatchedProductItem(
                                product_id=product.id,
                                name=product.name,
                                match_score=round(float(best_score), 2),
                                extracted_quantity=qty if (has_qty and not is_invalid and qty and qty > 0) else None,
                                quantity_missing=not has_qty or is_invalid or (qty is not None and qty <= 0),
                                is_ambiguous=False,
                            )
                        )
                        matched_product_ids.add(product.id)

                elif best_score >= AMBIGUOUS_MATCH_THRESHOLD:
                    if product.id not in matched_product_ids:
                        qty, is_invalid, has_qty = self.extract_quantity_from_phrase(best_clause)
                        matched_items.append(
                            MatchedProductItem(
                                product_id=product.id,
                                name=product.name,
                                match_score=round(float(best_score), 2),
                                extracted_quantity=qty if (has_qty and not is_invalid and qty and qty > 0) else None,
                                quantity_missing=not has_qty or is_invalid or (qty is not None and qty <= 0),
                                is_ambiguous=True,
                            )
                        )
                        matched_product_ids.add(product.id)

            return matched_items
        finally:
            if owns_session:
                session.close()

    def analyze(self, text: str, db: Optional[Session] = None) -> NLPAnalysisResult:
        """Perform comprehensive natural language analysis of customer message.

        Args:
            text: Customer message.
            db: Optional active SQLite database session.

        Returns:
            NLPAnalysisResult: Full structured analysis including intent, items, and flags.
        """
        cleaned_text = text.strip() if text else ""
        if not cleaned_text:
            return NLPAnalysisResult(
                original_text="",
                intent="unsupported",
                intent_confidence=0.0,
                matched_products=[],
                has_missing_quantities=False,
                needs_clarification=True,
                is_unsupported=True,
                clarification_reason="Received an empty customer message.",
            )

        intent, confidence = self.predict_intent(cleaned_text)
        matched_products = self.match_products(cleaned_text, db=db)

        # Detect missing quantities
        has_missing_quantities = any(p.quantity_missing for p in matched_products)
        has_ambiguous_products = any(p.is_ambiguous for p in matched_products)

        needs_clarification = False
        is_unsupported = False
        clarification_reason = None

        if intent == "unsupported":
            is_unsupported = True
            needs_clarification = True
            clarification_reason = "The request could not be mapped to a supported sales enquiry."
        elif intent in ("quotation_request", "product_inquiry") and not matched_products:
            needs_clarification = True
            clarification_reason = "Could not identify any matching product in the catalogue."
        elif has_ambiguous_products:
            needs_clarification = True
            clarification_reason = "Identified one or more ambiguous product matches requiring clarification."
        elif intent == "quotation_request" and has_missing_quantities:
            needs_clarification = True
            clarification_reason = "Quotation request is missing required quantities for one or more items."

        return NLPAnalysisResult(
            original_text=cleaned_text,
            intent=intent,
            intent_confidence=confidence,
            matched_products=matched_products,
            has_missing_quantities=has_missing_quantities,
            needs_clarification=needs_clarification,
            is_unsupported=is_unsupported,
            clarification_reason=clarification_reason,
        )


# Global NLP service singleton
nlp_service = NLPService()
