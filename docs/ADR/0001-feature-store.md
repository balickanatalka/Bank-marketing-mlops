---
title: Feature store decision
status: accepted
updated: 2026-11-02
---

# ADR 0001: No feature store at this stage

## Context

Lesson 4 has one pinned UCI tabular dataset, a chronological offline split and
one feature pipeline persisted with each classifier. There are no online feature
sources, shared feature consumers, point-in-time joins or deployed prediction API.

## Decision

Use `src/features/build.py:build_preprocessor()` inside the fitted scikit-learn
`Pipeline`. Training fits it only on train. Batch inference and the future API
must load the complete trusted pipeline and call `predict`/`predict_proba` without
refitting or reconstructing transforms. DVC tracks data, dependencies, parameters
and artifacts; the manifest pins raw SHA-256. A feature store adds operational
cost without solving an existing requirement here.

`unknown` represents an explicitly unknown categorical value. Education
`illiterate` means inability to read/write, not missing data; `nonexistent`
is the explicit previous-campaign outcome category in UCI additional-full.
Neither `unknown` nor `nonexistent` becomes NaN or an imputed category.
`pdays=999` means no previous contact: encode it as zero elapsed days plus a
separate indicator. True nulls are rejected by the raw contract; no imputer is
needed. The fitted scaler and encoder see only training rows.

Source: [UCI Bank Marketing](https://archive.ics.uci.edu/dataset/222/bank+marketing),
specifically `bank-additional/bank-additional-names.txt` in the official ZIP.
The website also describes older variants; their `pdays=-1` convention must not
be substituted for the selected additional-full variant.

## Consequences and review triggers

Tests compare batch versus a reconstructed single record, deterministic fits and
serialization round trips. This demonstrates a shared inference path, not a
running HTTP service. New online sources, several independent consumers or
point-in-time feature joins would justify revisiting a feature store.

Microsoft RAG remains future work over documentation and reports. It does not
require a feature store for this classifier and is not implemented in lesson 4.
