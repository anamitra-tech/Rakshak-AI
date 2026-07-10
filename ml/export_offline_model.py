"""
Exports ml.detector.ScamDetector's trained TF-IDF + LogisticRegression
pipeline to a compact, dependency-free text format the Android app's
MlScamScorer.kt can load and score against offline, without any ML
framework -- just tokenization + a sparse dot product + sigmoid.

Binary LogisticRegression only (classes_ == ['FRAUD', 'SAFE']): confirmed
empirically that predict_proba's P(FRAUD) == 1 / (1 + exp(decision_function)),
where decision_function == dot(x, coef_[0]) + intercept_[0] and x is the
FeatureUnion-concatenated, per-vectorizer-L2-normalized [word_tfidf | char_tfidf]
row. That exact formula is what MlScamScorer.kt reimplements; this script's
only job is to hand it the vocabulary/idf/coefficients it needs.

Output format (plain text, tab-separated fields, no JSON/binary library needed
on either the Python or Kotlin side):

  INTERCEPT\t<float>
  WORD_VOCAB\t<count>
  <term>\t<idf>\t<coef>          (one line per word vocabulary entry)
  ... (<count> lines)
  CHAR_VOCAB\t<count>
  <ngram>\t<idf>\t<coef>         (one line per char vocabulary entry)
  ... (<count> lines)

coef on each line is the LogisticRegression coefficient for that exact
feature's column in the concatenated [word | char] feature space -- i.e.
word coefficients are coef_[0][0:num_word_features] and char coefficients
are coef_[0][num_word_features:], sliced out here so Kotlin never has to
reconstruct the word/char offset itself.

Usage: python -m ml.export_offline_model
"""
import os

from ml.detector import ScamDetector

OUTPUT_PATH = os.path.join(
    "android", "app", "src", "main", "assets", "scam_model.txt"
)


def export():
    detector = ScamDetector()
    pipe = detector.pipe
    word_vec = pipe.named_steps["feat"].transformer_list[0][1]
    char_vec = pipe.named_steps["feat"].transformer_list[1][1]
    clf = pipe.named_steps["clf"]

    assert list(clf.classes_) == ["FRAUD", "SAFE"], (
        f"Export assumes binary classes_ == ['FRAUD', 'SAFE'], got {list(clf.classes_)}. "
        "The exported formula (P(FRAUD) = 1/(1+exp(decision))) is only valid for this "
        "exact class ordering -- re-derive it before exporting if this ever changes."
    )

    num_word = len(word_vec.vocabulary_)
    num_char = len(char_vec.vocabulary_)
    coef = clf.coef_[0]
    assert coef.shape[0] == num_word + num_char

    word_coef = coef[:num_word]
    char_coef = coef[num_word:]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(f"INTERCEPT\t{float(clf.intercept_[0])!r}\n")

        f.write(f"WORD_VOCAB\t{num_word}\n")
        # vocabulary_ maps term -> column index; write rows in index order
        # so Kotlin can read sequentially without needing to sort.
        word_terms_by_index = sorted(word_vec.vocabulary_.items(), key=lambda kv: kv[1])
        for term, idx in word_terms_by_index:
            f.write(f"{term}\t{float(word_vec.idf_[idx])!r}\t{float(word_coef[idx])!r}\n")

        f.write(f"CHAR_VOCAB\t{num_char}\n")
        char_terms_by_index = sorted(char_vec.vocabulary_.items(), key=lambda kv: kv[1])
        for term, idx in char_terms_by_index:
            f.write(f"{term}\t{float(char_vec.idf_[idx])!r}\t{float(char_coef[idx])!r}\n")

    print(f"Exported {num_word} word terms + {num_char} char terms to {OUTPUT_PATH}")
    print(f"Intercept: {float(clf.intercept_[0])!r}")


if __name__ == "__main__":
    export()
