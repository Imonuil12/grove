---
description: Automatically maintain and update ARCHITECTURE.md when backend, database, or frontend features change.
globs: ["app/backend/**", "app/frontend/**", "ARCHITECTURE.md"]
---

# Architecture Documentation Auto-Sync Rule

## Objective
Ensure that [ARCHITECTURE.md](../../ARCHITECTURE.md) remains an accurate, up-to-date representation of the Grove codebase whenever features, API endpoints, database schemas, or chatbot components are modified.

## Rules for Agents & Developers
1. **API Endpoint Changes**: Whenever a new API endpoint is added or an existing request/response structure is modified in `app/backend/main.py`, update the **Backend Services & API Specification** section in `ARCHITECTURE.md`.
2. **Database Schema Changes**: Whenever database models in `app/backend/models.py` are created, updated, or removed, update the **Database Schema & Models** section in `ARCHITECTURE.md`.
3. **Chatbot Engine Logic**: Whenever intent matching, LLM integration, safety guardrails, or archetype processing logic in `main.py` is altered, update the **Chatbot Engine Architecture** section in `ARCHITECTURE.md`.
4. **Directory / Tech Stack Updates**: Keep directory structure maps and dependency tables synchronized with changes to the project.
