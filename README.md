# Job Agent AI

> **Production-grade autonomous AI job search platform powered by multi-agent workflows, LangGraph, LLMs, Playwright, PostgreSQL, and Qdrant.**

## Overview

Job Agent AI is a distributed, agentic AI platform that automates the end-to-end job application workflow for a single user.

Instead of being a browser automation script, the system is designed as a collection of specialized AI agents orchestrated through LangGraph.

The platform is capable of:

* Discovering new job opportunities
* Parsing and understanding job descriptions
* Matching jobs against a master resume
* Tailoring resumes for ATS optimization
* Generating personalized cover letters
* Automatically submitting applications using Playwright
* Tracking application status
* Monitoring recruiter emails
* Preparing interview material

---

# Features

### Job Discovery

* LinkedIn
* Greenhouse
* Lever
* Wellfound
* YC Jobs
* Company Career Pages

### Resume Intelligence

* ATS score
* Resume tailoring
* Skill gap analysis
* Resume versioning

### Application Automation

* Browser automation
* Resume upload
* Cover letter upload
* Form filling
* Confirmation capture

### Application Tracking

* Application history
* Recruiter responses
* Interview tracking
* Offers
* Rejections

### AI Agents

* Job Discovery Agent
* JD Parser Agent
* Resume Match Agent
* Resume Tailoring Agent
* Cover Letter Agent
* Application Agent
* Email Monitor Agent
* Follow-up Agent
* Interview Preparation Agent

---

# Architecture

The platform follows a distributed multi-agent architecture.

```text
Dashboard
      │
      ▼
FastAPI Backend
      │
      ▼
LangGraph Orchestrator
      │
      ▼
AI Agents
      │
      ▼
PostgreSQL + Qdrant + Redis
      │
      ▼
Playwright Worker
```

---

# Tech Stack

## Backend

* Python 3.13
* FastAPI
* SQLAlchemy
* Alembic
* Pydantic
* uv

## Frontend

* Next.js
* TypeScript
* TailwindCSS
* shadcn/ui

## AI

* LangGraph
* Gemini Flash
* Claude Sonnet
* GPT-5.5
* Voyage AI Embeddings

## Infrastructure

* Docker
* Docker Compose
* PostgreSQL
* Redis
* Qdrant

## Browser Automation

* Playwright

---

# Project Structure

```text
job-agent-ai/

backend/
frontend/
workers/
shared/
infrastructure/
docs/
scripts/
.github/
```

---

# Roadmap

## Phase 1

* Project foundation
* Infrastructure
* Docker
* Backend scaffold
* Frontend scaffold

## Phase 2

* Database
* Migrations
* Repository layer
* APIs

## Phase 3

* Dashboard

## Phase 4

* Job Discovery Agent

## Phase 5

* Resume Matching Agent

## Phase 6

* Resume Tailoring Agent

## Phase 7

* Cover Letter Generation

## Phase 8

* Playwright Worker

## Phase 9

* Email Monitoring

## Phase 10

* Interview Preparation

---

# Development Workflow

```text
feature/*
      │
      ▼
staging
      │
      ▼
main
```

---

# Design Principles

* Feature-first architecture
* Modular components
* Production-ready
* Strong typing
* Structured logging
* Async-first
* Dependency injection
* Scalable by design
* Human-in-the-loop for critical decisions

---

# Status

🚧 Currently under active development.

The project is being built incrementally, with each phase focusing on a single architectural milestone before introducing AI functionality.

---

# License

MIT License
