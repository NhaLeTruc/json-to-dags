# Architecture Decision Records (ADR)

This directory contains Architecture Decision Records for the Apache Airflow ETL Demo Platform.

## What is an ADR?

An Architecture Decision Record (ADR) captures an important architectural decision made along with its context and consequences.

## Format

Each ADR follows this structure:

1. **Title**: A short descriptive title
2. **Status**: Proposed, Accepted, Deprecated, Superseded
3. **Context**: The issue motivating this decision
4. **Decision**: The change that we're proposing or have agreed to
5. **Consequences**: The results of applying this decision

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [001](./001-airflow-version-downgrade.md) | Downgrade from Airflow 3.1.0 to 2.10.5 | Accepted | 2025-11-14 |

## Creating a New ADR

1. Copy the template from an existing ADR
2. Use sequential numbering: `00X-title-in-kebab-case.md`
3. Fill in all sections with relevant information
4. Update this README index
5. Submit for review via pull request

## References

- [ADR GitHub Organization](https://adr.github.io/)
- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
