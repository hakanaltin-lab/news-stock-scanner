# AURORA AI CIO v3.1

# Import Architecture Blueprint v1.0


## Purpose

This document defines the official Python import architecture of AURORA AI CIO.

The objective is to ensure:

- Clean dependencies
- No circular imports
- Clear module ownership
- Scalable architecture


Core principle:

> Dependencies flow downward. Control flows through orchestration.


---

# 1. Official Layer Hierarchy


```text
                    CORE

                      ↓

                  MARKET

                      ↓

              INTELLIGENCE

                      ↓

                 RESEARCH

                      ↓

                   ALPHA

                      ↓

                PORTFOLIO

                      ↓

                    RISK

                      ↓

                 DECISION

                      ↓

                EXECUTION

                      ↓

                 JOURNAL

                      ↓

                DASHBOARD
