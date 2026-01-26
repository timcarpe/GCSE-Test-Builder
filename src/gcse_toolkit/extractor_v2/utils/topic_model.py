"""
Runtime wrapper for the supervised topic classifier that uses
regex pattern matches as binary features.

This is used downstream by the slicer / builder to classify
question text into topics, using a model trained offline and
stored in the plugin data folder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import joblib
import numpy as np
import re


COMMANDS = ["calculate", "describe", "explain", "state", "determine"]

def preprocess_text(text: str) -> str:
    """Refined preprocessing pass (Phases 2 & 3). Matches build_model.py."""
    if not text:
        return ""
    # Standard normalization
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\x00-\x1f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()

    # 1. Typed Tokens (UNIT_VALUE, OPERATOR, RATE)
    text = re.sub(r"\b\d+(\.\d+)?\s*(m/s|kg|J|V|cm\^3|mb|gb|kb|hz|ghz|bit|byte|ms|s|%)\b", " UNIT_VALUE ", text)
    text = re.sub(r"[+\-*/^=≥≤<>]", " OPERATOR ", text)
    text = re.sub(r"\bper\b", " RATE ", text)
    
    # 2. Command Tags (CMD_*)
    for c in COMMANDS:
        if re.search(r"\b" + re.escape(c) + r"\b", text):
            text += f" CMD_{c.upper()} "
            
    # 3. Notation preservation (symbols like ²)
    if "²" in text or "³" in text:
        text += " NOTATION_POWER "
        
    return text


class TopicModel:
    """Supervised topic classifier using regex + structural n-gram features."""

    def __init__(self, model_path: Path) -> None:
        bundle = joblib.load(model_path)
        self.model = bundle["model"]
        self.pattern_index: Dict[str, int] = bundle["pattern_index"]
        self.topics = bundle["topics"]
        self.exam_code = bundle.get("exam_code")
        
        # Phase 1-3 Support
        self.vectorizer = bundle.get("vectorizer")
        self.poly = bundle.get("poly")
        
        # Feature interaction support (legacy pattern combinations)
        self.interaction_indices: Optional[list] = bundle.get("interaction_indices")
        
        # Phase 6: Confusion Classifiers
        self.confusion_clfs: Dict[str, any] = bundle.get("confusion_clfs", {})
        
        # Dynamic threshold calculated during training (per exam code)
        self.optimal_threshold: float = bundle.get("optimal_threshold", 0.6)

        # Precompile regex patterns
        self._compiled = {
            pat: re.compile(pat, re.IGNORECASE)
            for pat in self.pattern_index.keys()
        }
        self._num_patterns = len(self.pattern_index)

    def _vectorize(self, text: str):
        """Build a feature vector for the given text (Phases 1-3 compatibility)."""
        from scipy.sparse import lil_matrix, hstack, csr_matrix
        
        # 1. Preprocess structural tokens
        text = preprocess_text(text)
        
        # 2. Regex patterns (Binary)
        x_regex = lil_matrix((1, self._num_patterns), dtype=np.float32)
        for pat, j in self.pattern_index.items():
            if self._compiled[pat].search(text):
                x_regex[0, j] = 1.0
        
        x_regex = x_regex.tocsr()
        
        # 3. Structural Features (Phase 1 Vectorizer)
        if self.vectorizer:
            x_structural = self.vectorizer.transform([text])
            x_final = hstack([x_regex, x_structural]).tocsr()
        else:
            x_final = x_regex
            
        # 4. Interactions (Phase 3)
        if self.interaction_indices and self.poly:
            x_interact = x_final[:, self.interaction_indices].toarray()
            x_poly = self.poly.transform(x_interact)
            n_int = len(self.interaction_indices)
            x_int_only = x_poly[:, n_int:]
            x_final = hstack([x_final, csr_matrix(x_int_only)]).tocsr()
            
        return x_final

    def predict_with_confidence(self, text: str) -> Tuple[Optional[str], float]:
        """Return (topic_name or None, confidence [0,1]) with second-pass disambiguation."""
        x = self._vectorize(text)
        
        # Use calibrated probability if available
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(x)[0]
            idx = int(proba.argmax())
            conf = float(proba[idx])
            topic = self.topics[idx]
            
            # Phase 6: Second-Pass Disambiguation
            if self.confusion_clfs:
                try:
                    # Find top 2 topics
                    top2_idx = proba.argsort()[-2:][::-1]
                    t1, t2 = self.topics[top2_idx[0]], self.topics[top2_idx[1]]
                    pair_key = "__vs__".join(sorted([t1, t2]))
                    
                    if pair_key in self.confusion_clfs:
                        bin_clf = self.confusion_clfs[pair_key]
                        # Logic in build_model was: y_bin_map = [1 if a else 0] where pair = tuple(sorted([a, b]))
                        # Sorted order gives us mapping
                        a, b = sorted([t1, t2])
                        bin_prob = bin_clf.predict_proba(x)[0] # [P(0), P(1)] -> [P(b), P(a)]
                        
                        winner_idx = int(bin_prob.argmax())
                        winner_topic = a if winner_idx == 1 else b
                        winner_conf = float(bin_prob[winner_idx])
                        
                        # If second-pass is confident, override
                        if winner_conf > 0.6:
                            return winner_topic, (conf + winner_conf) / 2.0
                except Exception as e:
                    # Fallback to primary model if ensemble fails (e.g. feature mismatch)
                    pass
            
            return topic, conf
        else:
            # Fallback to decision_function (Legacy)
            decision = self.model.decision_function(x)
            if decision.ndim == 1:
                idx = int(decision >= 0)
                conf = float(abs(decision[0]))
            else:
                idx = int(decision.argmax())
                conf = float(decision.max())
            return self.topics[idx], conf

    def predict(self, text: str, min_conf: Optional[float] = None) -> Optional[str]:
        """Return topic_name if confidence >= threshold, else None."""
        topic, conf = self.predict_with_confidence(text)
        
        # Use provided min_conf or fall back to model's optimal threshold
        threshold = min_conf if min_conf is not None else self.optimal_threshold
        
        if topic is None or conf < threshold:
            return None
        return topic

    def get_probabilities(self, text: str) -> Dict[str, float]:
        """Return the probability distribution for all topics."""
        if not hasattr(self.model, "predict_proba"):
            # Fallback for models without probability calibration
            # Use decision function normalized strictly for relative comparison
            x = self._vectorize(text)
            decision = self.model.decision_function(x)
            if decision.ndim == 1:
                # Binary: sigmoid
                score = 1 / (1 + np.exp(-decision[0]))
                return {self.topics[0]: 1 - score, self.topics[1]: score}
            else:
                # Multiclass: softmax
                exp_scores = np.exp(decision - decision.max())  # shift for stability
                probs = exp_scores / exp_scores.sum()
                return {topic: float(prob) for topic, prob in zip(self.topics, probs[0])}

        x = self._vectorize(text)
        probas = self.model.predict_proba(x)[0]
        return {topic: float(prob) for topic, prob in zip(self.topics, probas)}
