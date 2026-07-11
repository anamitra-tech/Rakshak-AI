package com.rakshak.ai.intelligence

import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.sqrt

/**
 * Pure-arithmetic reimplementation of ml.detector.ScamDetector's trained
 * TF-IDF (word 1-2gram + char_wb 3-5gram) + binary LogisticRegression
 * pipeline -- no ML framework, just tokenization, a sparse dot product,
 * and a sigmoid. Reads its weights from the asset exported by
 * ml/export_offline_model.py (android/app/src/main/assets/scam_model.txt);
 * this class never trains anything itself.
 *
 * Every step here (lowercasing, the (?U)\b\w\w+\b word tokenizer, unigram+
 * bigram formation, the char_wb whitespace-padded n-gram algorithm,
 * sublinear_tf on the word side only, per-vectorizer L2 normalization
 * before concatenation, and P(FRAUD) = 1/(1+exp(decision_function))) was
 * copied from scikit-learn 1.7.1's actual source
 * (TfidfVectorizer._word_ngrams /._char_wb_ngrams / _preprocess, and
 * LogisticRegression's binary decision_function/predict_proba relationship
 * for classes_ == ["FRAUD", "SAFE"]) and cross-validated case-by-case
 * against the real Python model -- see check_offline_ml_scorer.py. If
 * ml/detector.py's vectorizer settings ever change (ngram ranges, min_df,
 * sublinear_tf, or the class set stops being binary FRAUD/SAFE), this file
 * and the exporter both need re-deriving from scratch, not just re-running.
 */
object MlScamScorer {

    data class Model(
        val intercept: Double,
        val wordVocab: Map<String, TermWeights>,
        val charVocab: Map<String, TermWeights>,
    )

    data class TermWeights(val idf: Double, val coef: Double)

    // No (?U) flag: Android's regex engine is ICU-native (com.android.icu.util.regex),
    // not OpenJDK's, and doesn't support the (?U)/UNICODE_CHARACTER_CLASS embedded-flag
    // syntax at all -- compiling it threw PatternSyntaxException at class-init time,
    // crashing the app on every offline-fallback use. \w and \b are Unicode-aware on
    // Android by default (unlike desktop java.util.regex, where \w is ASCII-only unless
    // this flag or UNICODE_CHARACTER_CLASS is set), so dropping the flag entirely is the
    // fix, not a workaround -- see check_ml_scorer_parity.py's re-run after this change,
    // which re-validates Devanagari-containing cases specifically.
    private val WORD_TOKEN_PATTERN = Regex("\\b\\w\\w+\\b")
    private val WHITESPACE_SPLIT = Regex("\\s+")

    fun parseModel(raw: String): Model {
        val lines = raw.split("\n").map { it.trimEnd('\r') }
        var i = 0

        require(lines[i].startsWith("INTERCEPT\t")) { "Expected INTERCEPT line, got: ${lines[i]}" }
        val intercept = lines[i].substringAfter("\t").toDouble()
        i++

        require(lines[i].startsWith("WORD_VOCAB\t")) { "Expected WORD_VOCAB line, got: ${lines[i]}" }
        val numWord = lines[i].substringAfter("\t").toInt()
        i++
        val wordVocab = HashMap<String, TermWeights>(numWord * 2)
        for (n in 0 until numWord) {
            val parts = lines[i].split("\t")
            wordVocab[parts[0]] = TermWeights(parts[1].toDouble(), parts[2].toDouble())
            i++
        }

        require(lines[i].startsWith("CHAR_VOCAB\t")) { "Expected CHAR_VOCAB line, got: ${lines[i]}" }
        val numChar = lines[i].substringAfter("\t").toInt()
        i++
        val charVocab = HashMap<String, TermWeights>(numChar * 2)
        for (n in 0 until numChar) {
            val parts = lines[i].split("\t")
            charVocab[parts[0]] = TermWeights(parts[1].toDouble(), parts[2].toDouble())
            i++
        }

        return Model(intercept, wordVocab, charVocab)
    }

    /** Word tokenizer: sklearn's default token_pattern r"(?u)\b\w\w+\b" on lowercased text. */
    private fun wordTokens(lowered: String): List<String> =
        WORD_TOKEN_PATTERN.findAll(lowered).map { it.value }.toList()

    /** Unigrams (as-is) followed by bigrams (adjacent-token space-joins) -- TfidfVectorizer._word_ngrams
     *  for ngram_range=(1,2): bigrams are formed from the tokenized list, so a dropped single-char
     *  token (e.g. "3") is skipped over, not treated as a gap. */
    private fun wordNgrams(tokens: List<String>): List<String> {
        if (tokens.isEmpty()) return emptyList()
        val result = ArrayList<String>(tokens.size * 2)
        result.addAll(tokens)
        for (idx in 0 until tokens.size - 1) {
            result.add(tokens[idx] + " " + tokens[idx + 1])
        }
        return result
    }

    /** TfidfVectorizer._char_wb_ngrams, byte-for-byte: pad each whitespace-split "word" (from the
     *  raw lowercased text, NOT the word tokenizer's \w+ filtering -- punctuation/digits/single
     *  chars are all included here) with a single leading/trailing space, then emit every
     *  contiguous substring of length 3, then 4, then 5, short-word edge case included. */
    private fun charWbNgrams(lowered: String): List<String> {
        val words = lowered.trim().split(WHITESPACE_SPLIT).filter { it.isNotEmpty() }
        val result = ArrayList<String>()
        for (word in words) {
            val w = " $word "
            val wLen = w.length
            var n = 3
            while (n <= 5) {
                var offset = 0
                result.add(w.substring(offset, minOf(offset + n, wLen)))
                while (offset + n < wLen) {
                    offset += 1
                    result.add(w.substring(offset, offset + n))
                }
                if (offset == 0) break // short word (wLen < n): counted once, stop growing n
                n += 1
            }
        }
        return result
    }

    private fun termCounts(terms: List<String>): Map<String, Int> {
        val counts = HashMap<String, Int>(terms.size * 2)
        for (t in terms) counts[t] = (counts[t] ?: 0) + 1
        return counts
    }

    /** Sparse L2-normalized-TF-IDF dot product with this part's coefficient slice, computed without
     *  materializing the full (1407- or 5341-wide) dense vector: numerator = sum(rawTfidf * coef)
     *  over matched terms only, norm = sqrt(sum(rawTfidf^2)) over the same matched terms (unmatched
     *  vocab entries are 0 and don't affect either sum), contribution = numerator / norm. */
    private fun partContribution(
        counts: Map<String, Int>,
        vocab: Map<String, TermWeights>,
        sublinearTf: Boolean,
    ): Double {
        var numerator = 0.0
        var sumSq = 0.0
        for ((term, count) in counts) {
            val weights = vocab[term] ?: continue // out-of-vocabulary: contributes 0, same as sklearn's transform()
            val tf = if (sublinearTf) 1.0 + ln(count.toDouble()) else count.toDouble()
            val rawTfidf = tf * weights.idf
            numerator += rawTfidf * weights.coef
            sumSq += rawTfidf * rawTfidf
        }
        if (sumSq == 0.0) return 0.0
        return numerator / sqrt(sumSq)
    }

    /** Returns P(FRAUD) in [0, 1]. Mirrors ml.detector.ScamDetector.predict()'s own empty-text guard
     *  (returns 0.0 rather than running the model on nothing). */
    fun scoreFraudProbability(model: Model, text: String): Double {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return 0.0

        val lowered = trimmed.lowercase()
        val wordCounts = termCounts(wordNgrams(wordTokens(lowered)))
        val charCounts = termCounts(charWbNgrams(lowered))

        val wordContribution = partContribution(wordCounts, model.wordVocab, sublinearTf = true)
        val charContribution = partContribution(charCounts, model.charVocab, sublinearTf = false)

        val decision = wordContribution + charContribution + model.intercept
        // classes_ == ["FRAUD", "SAFE"]: decision_function > 0 predicts SAFE (classes_[1]), so
        // P(FRAUD) = 1 - sigmoid(decision) = sigmoid(-decision) = 1 / (1 + exp(decision)).
        return 1.0 / (1.0 + exp(decision))
    }
}
