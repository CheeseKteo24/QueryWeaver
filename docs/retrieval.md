# Retrieval design notes

## 1. Why Chinese needs a different lexical baseline

The original regular expression treated a complete Chinese sentence as one token. A query such as `退款申请` could not exactly match the token `客户可以提交退款申请`. The dependency-free baseline now emits characters and overlapping character bigrams such as `退`, `款`, and `退款`.

This is deliberately a baseline. Character n-grams improve recall but can create noisy matches. A production system should benchmark a learned segmenter or model tokenizer rather than assuming one tokenizer is universally best.

## 2. Why raw retrieval scores are not added

BM25 and cosine similarity have different ranges and distributions. Adding `0.7 * bm25 + 0.3 * cosine` makes the weights dependent on the corpus and implementation. Reciprocal Rank Fusion (RRF) uses rank instead:

```text
score(document) = sum(1 / (k + rank_i(document)))
```

A document that ranks well in multiple retrievers receives more evidence. The constant `k` controls how strongly top positions dominate.

## 3. Why the local vector implementation is not called semantic

`HashingEmbedder` maps lexical tokens into a fixed-size vector. It is deterministic, fast, and suitable for tests, but it does not understand that “holiday” can mean “annual leave.” Calling it an embedding baseline keeps CI offline while preserving the provider contract for a real multilingual embedding model.

## 4. What the benchmark tells us

The fixture contains direct keyword questions in English and Chinese plus English paraphrases with no token overlap. The expected baseline result is:

| Retriever | Hit rate@3 | MRR@3 | Recall@3 |
|---|---:|---:|---:|
| BM25-style lexical | 0.800 | 0.800 | 0.800 |
| Hashing vector | 0.800 | 0.800 | 0.800 |
| Hybrid RRF | 0.800 | 0.800 | 0.800 |

The 0.200 gap is intentional. M1's real multilingual embedding adapter must close it without regressing the direct keyword cases or unacceptable latency.
