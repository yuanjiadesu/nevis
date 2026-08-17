## Purpose

Makes the existing search and repository harnesses emit comparable, credential-safe reports.

## ADDED Requirements

### Requirement: Existing harnesses emit named reports

The system MUST identify each run as one of:

- `search_eval`: labelled seed cases, including spelling retries
- `search_warm_p95`: one warmed query, sequential
- `repo_capacity`: rollback-only repository branches on synthetic rows

A run MUST NOT mix those workloads into one p95 or pass/fail.

#### Scenario: Distinct workloads stay distinct

- **WHEN** an operator runs `search_eval` and `search_warm_p95`
- **THEN** each report names its own workload and the evaluation-set p95 is not used as the one-query API p95

### Requirement: Every report includes comparable context

Every report MUST include timestamp, workload, ranking version when search ran, corpus counts when a database was used, concurrency, warm-up, host or runtime identity, p50, p95, the SLO that was applied, and pass or fail.

Reports MUST NOT include raw queries, document text, emails, vectors, tokens, or connection strings.

#### Scenario: A report is comparable

- **WHEN** two runs use the same workload, ranking version, corpus shape, warm-up, and concurrency
- **THEN** their p95 values MAY be compared

#### Scenario: A report is not comparable

- **WHEN** two runs differ in host, corpus, warm-up, concurrency, or ranking version
- **THEN** the system MUST treat them as incomparable

### Requirement: One-pass search has an 800 ms p95 objective

`search_warm_p95` MUST fail when the warmed sequential p95 exceeds 800 ms. Spelling-retry cases MUST NOT be included in that gate.

#### Scenario: Warm search meets the objective

- **WHEN** a warmed sequential `search_warm_p95` run has p95 at or below 800 ms
- **THEN** the report is pass

#### Scenario: Warm search misses the objective

- **WHEN** a warmed sequential `search_warm_p95` run has p95 above 800 ms
- **THEN** the report is fail

### Requirement: Repository default fits Compose memory

`repo_capacity` MUST default to a size that can finish on the Compose memory limit. 10,000 clients / 100,000 documents MUST be opt-in.

#### Scenario: Default repository harness finishes

- **WHEN** an operator runs `repo_capacity` with no size override
- **THEN** the run completes, rolls back synthetic rows, and reports branch and combined p95

### Requirement: Documentation describes how to measure, not last-run stats

Operator documentation MUST state the three workloads, the 800 ms gate, the commands, and the comparability rule. It MUST NOT be the source of truth for a dated laptop ledger.

#### Scenario: Docs stay a how-to

- **WHEN** an operator opens the performance guide
- **THEN** they can run a harness and read a JSON report without treating previous host numbers as current fact
