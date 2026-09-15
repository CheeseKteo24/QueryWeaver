# Retrieval design notes

## RRF 在实际工作中的作用

企业检索同时存在两类信号：错误码、产品名、合同编号等需要精确匹配；口语化问题、同义改写和跨语言问题更依赖向量语义。BM25 分数和 cosine 分数不在同一量纲，直接相加需要持续做分数校准。RRF 只使用每一路的排名，把异构检索结果合并成一个候选集。

它适合：

- BM25 与 dense 各自能找回一部分独特相关文档；
- 多个索引或检索服务的原始分数无法直接比较；
- 希望先建立稳定、低调参成本的 hybrid baseline。

它不解决：

- 两路都没有召回相关文档；
- Chunk 本身缺失或切分错误；
- 最终候选的细粒度语义排序；
- 答案生成阶段的幻觉。

因此实际评估顺序是：先比较 lexical/dense 的候选召回互补性，再看 RRF 是否提高 Recall@K/MRR，最后用 CrossEncoder 重排。若 RRF 在足够大的真实数据集上没有稳定收益，就不应因为架构图好看而保留它。

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

The fixture contains 16 confusable English and Chinese chunks and 20 questions, including direct keyword queries, policy variants, identity variants, and paraphrases with little token overlap. One local baseline run produced:

| Retriever | Hit rate@3 | MRR@3 | Recall@3 |
|---|---:|---:|---:|
| BM25-style lexical | 0.900 | 0.850 | 0.900 |
| Hashing vector | 0.850 | 0.800 | 0.850 |
| Hybrid RRF | 0.900 | 0.825 | 0.900 |
| Hybrid + token reranker | 0.900 | 0.825 | 0.900 |

The token reranker validates candidate expansion and score replacement but does not improve semantic quality. A real cross-encoder must prove its value without reducing candidate recall or causing unacceptable p95 latency.
