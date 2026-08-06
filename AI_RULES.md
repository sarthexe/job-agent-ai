# AI_RULES.md

# AI Job Agent — AI Development Rules

## Project Overview

This project is a production-grade autonomous AI job search platform designed for a single user.

The system should be modular, scalable, maintainable, and production-ready from day one.

The objective is **not** to build a simple automation script but a distributed multi-agent system capable of:

* Discovering jobs
* Parsing job descriptions
* Matching resumes
* Tailoring resumes
* Generating cover letters
* Applying automatically using Playwright
* Tracking applications
* Monitoring recruiter emails
* Preparing interview material

---

# Core Architecture Principles

Always follow these principles:

* Feature-first architecture (DDD-inspired)
* Single Responsibility Principle
* Separation of Concerns
* Composition over inheritance
* Dependency Injection
* Async-first whenever appropriate
* Stateless services whenever possible
* Observable and well logged
* Easy to replace any implementation without affecting the rest of the system

Never tightly couple modules.

---

# Technology Stack

## Backend

* Python 3.13
* FastAPI
* SQLAlchemy 2.x
* Alembic
* Pydantic v2
* uv
* Ruff

## Frontend

* Next.js
* TypeScript
* TailwindCSS
* shadcn/ui
* Zustand
* TanStack Query

## Infrastructure

* Docker
* Docker Compose
* PostgreSQL
* Redis
* Qdrant

## AI

* LangGraph
* Gemini Flash
* Claude Sonnet
* GPT-5.5
* Voyage AI Embeddings

---

# Architecture

Use Feature-First Architecture.

Example:

backend/app/

```
job_discovery/
    api.py
    service.py
    repository.py
    schemas.py
    models.py

resume/
    api.py
    service.py
    repository.py
    schemas.py
    models.py

application/
    ...

email/
    ...

shared/
    config/
    database/
    logging/
    utils/
```

Do NOT organize the project by models/, services/, repositories/ at the root level.

Each feature owns its implementation.

---

# Coding Standards

Always follow:

* PEP8
* Ruff formatting
* Type hints everywhere
* Docstrings for all public functions
* No wildcard imports
* No unnecessary comments
* No dead code
* Keep functions small
* Keep files reasonably sized
* Prefer readability over cleverness

---

# Naming Convention

Python files

snake_case.py

Classes

PascalCase

Variables

snake_case

Constants

UPPER_CASE

Environment variables

UPPER_CASE

API endpoints

kebab-case where appropriate

---

# Async Rules

Prefer async for:

* Database access
* HTTP requests
* AI model calls
* Queue operations
* Browser communication

Avoid blocking operations.

---

# Database Rules

Use:

* PostgreSQL
* SQLAlchemy ORM
* Alembic migrations

Never execute raw SQL unless absolutely necessary.

Primary keys should use UUID.

Store timestamps in UTC.

---

# Configuration Rules

Never call os.getenv() directly in business logic.

All configuration must come from a centralized Settings class.

---

# Logging Rules

Never use print().

Always use structured logging.

Every log should include:

* module
* event
* execution time
* status
* error (if any)

---

# API Rules

All APIs must live under:

/api/v1/

Examples:

/api/v1/jobs

/api/v1/resumes

/api/v1/applications

/api/v1/system

---

# Agent Rules

Each agent must have a single responsibility.

Agents should never communicate directly with one another.

Communication happens through:

* LangGraph
* Database
* Queue

Agents should receive structured input and return structured output.

---

# Model Assignment

Gemini Flash

* Job parsing
* Skill extraction
* Resume matching
* Email classification
* Data extraction
* Categorization

Claude Sonnet

* Resume tailoring
* Cover letters
* Follow-up emails
* Recruiter replies
* Interview preparation

GPT-5.5

* Final review
* Edge-case reasoning
* Browser fallback decisions
* Complex judgment

---

# Prompt Rules

Prompts must never be hardcoded.

Store prompts inside:

shared/prompts/

Each prompt should have:

* Version
* Purpose
* Input schema
* Output schema

---

# Worker Rules

Workers are independent services.

Each worker should expose a consistent interface.

Workers should not directly modify unrelated features.

Workers communicate through APIs, queues, and the database.

---

# Playwright Rules

Playwright is deterministic.

Do not use LLMs for browser navigation unless an unexpected situation occurs.

Always:

* Capture screenshots
* Log actions
* Save failures
* Retry safely

---

# Error Handling

Every external call must have:

* Retry logic
* Timeout
* Logging
* Meaningful exceptions

Never silently ignore failures.

---

# Testing Rules

All new services should be testable.

Prefer pytest.

Keep business logic independent from FastAPI routes.

---

# Git Workflow

Branches:

main

staging

feature/<feature-name>

Never commit directly to main.

Use Pull Requests.

---

# Commit Style

Examples:

feat: add discovery agent

fix: resolve postgres migration issue

refactor: simplify repository layer

docs: update architecture

---

# Documentation

Keep the following files updated:

docs/

architecture.md

database.md

agents.md

workflows.md

api.md

deployment.md

roadmap.md

---

# General Philosophy

Build software that is:

* Modular
* Maintainable
* Observable
* Scalable
* Production-ready
* Easy to understand
* Easy to extend

Prioritize clean architecture over quick implementation.
