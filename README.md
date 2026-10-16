# B2B Growth Platform

An AI-powered B2B lead generation and outreach platform that helps businesses discover, qualify, engage, and manage potential customers from one application.

Instead of asking business owners to connect and orchestrate multiple tools themselves, the platform brings the workflow into a single workspace: define the business context and ideal customer profile (ICP), discover relevant leads, qualify and enrich their records, manage outreach across connected channels, and track results through a built-in CRM and analytics dashboard.

> **Project status:** In development. This README describes the intended product and proposed architecture; individual integrations and features may not be implemented yet.

## Table of Contents

- [Problem](#problem)
- [Solution](#solution)
- [Core Workflow](#core-workflow)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [AI Agents and Background Workers](#ai-agents-and-background-workers)
- [Data and Integrations](#data-and-integrations)
- [Security and Responsible Outreach](#security-and-responsible-outreach)
- [Development Roadmap](#development-roadmap)
- [Local Development](#local-development)
- [Project Structure](#project-structure)
- [Contributing](#contributing)

## Problem

B2B lead generation often requires repetitive manual work across disconnected tools. Teams must understand their target market, search multiple sources, identify suitable companies, find contact details, write personalized messages, manage replies, update spreadsheets or CRMs, and report on performance.

This process is time-consuming, difficult to scale, and often depends on employees manually coordinating many separate services.

## Solution

The B2B Growth Platform aims to automate this workflow through a unified, multi-tenant SaaS application.

A business owner configures the company profile, products or services, target market, ICP, outreach preferences, and available communication channels. The platform then runs a controlled workflow to discover potential customers, evaluate their fit, prepare outreach, track interactions, update the CRM, and report on outcomes.

The product is designed for business users who should not need programming or AI expertise to operate the system.

## Core Workflow

1. **Configure business context** — Add company details, products, target markets, qualification rules, and supporting documents such as PDF or Markdown files.
2. **Define the ICP** — Specify target industries, company size, locations, buyer roles, inclusion criteria, and exclusion criteria.
3. **Discover leads** — Search through configured and permitted data sources, such as search providers and business directories.
4. **Qualify and enrich** — Deduplicate results, evaluate ICP fit, record the evidence behind each score, and find or validate available business contact information.
5. **Prepare outreach** — Generate context-aware message drafts for enabled channels.
6. **Engage through connected channels** — Send and receive messages through supported integrations, subject to provider capabilities and applicable rules.
7. **Manage the CRM pipeline** — Track lead status, conversations, activities, follow-ups, meetings, proposals, and outcomes.
8. **Analyze performance** — Report on qualification rates, delivery and reply rates, channel performance, conversion, and reasons for lost opportunities.
9. **Improve over time** — Use recorded outcomes to inform future qualification criteria and messaging, with changes kept reviewable and controlled.

## Key Features

### Business Context and ICP

- Workspace-level company profile and product information.
- Upload and process business documents.
- Editable ICP configuration and qualification criteria.
- Campaign-specific target markets and exclusion rules.

### Lead Discovery and Qualification

- Pluggable lead-source adapters.
- Lead normalization and deduplication.
- Qualification scores with explanations and source evidence.
- Contact enrichment and verification where supported.
- Clear handling of incomplete, low-confidence, or unavailable data.

### Outreach Automation

- Personalized message drafting using company context and lead information.
- Configurable outreach policies and follow-up schedules.
- Human approval options before sending.
- Retry handling, rate limits, and delivery-state tracking.
- Stop conditions for opt-outs, negative replies, and other suppression rules.

### Built-in CRM

- Searchable leads and contacts table.
- Configurable pipeline stages.
- Company and contact detail pages.
- Conversation history and activity timeline.
- Manual actions and follow-up management.
- Duplicate prevention and auditable stage changes.

### Channel Connections

Users can connect and configure supported communication channels from the application. Email is a proposed first channel; other integrations, such as WhatsApp and Telegram, depend on the supported APIs, account types, permissions, and provider policies.

The platform should verify a connection before enabling it for outreach and should clearly show connection health and supported capabilities. At least one usable outreach channel should be configured before automated outreach is enabled.

### Analytics and Reporting

- Lead discovery and qualification metrics.
- Delivery, reply, and positive-reply rates.
- Meeting and opportunity conversion.
- Response-time and follow-up metrics.
- Channel and campaign comparisons.
- Lost-lead reasons and outcome tracking.

## Architecture

The proposed starting point is a **modular monolith with separate background workers**. This keeps the core product straightforward to develop while allowing long-running tasks to scale independently.

```text
React Web Application
        |
        v
NestJS REST API
        |
        +-------------------- PostgreSQL
        |                      Persistent business data
        |
        +-------------------- Redis + BullMQ
                               Background job queues
                                      |
                +---------------------+---------------------+
                |                     |                     |
         Discovery Worker        AI Worker           Outreach Worker
                |                     |                     |
          Search adapters       LLM adapters       Messaging adapters

                         Document Processing Worker
                                  |
                            Object Storage
```

### Main Components

- **Web application:** Workspace setup, campaign management, lead review, CRM, channel settings, and analytics.
- **API:** Authentication, authorization, workspace management, business logic, CRUD endpoints, and orchestration.
- **PostgreSQL:** Persistent records for workspaces, ICPs, campaigns, leads, contacts, messages, activities, and agent runs.
- **Redis and BullMQ:** Queuing, delayed jobs, retries, concurrency control, and background processing.
- **AI layer:** Provider-independent interface for language models used for context extraction, qualification, research assistance, message drafting, and reply classification.
- **Source adapters:** Consistent interfaces for configured lead-discovery providers.
- **Messaging adapters:** Consistent interfaces for email and other supported channels.
- **Object storage:** Uploaded documents and processed artifacts.
- **Analytics:** Metrics derived from persisted events and CRM outcomes.

External providers remain dependencies for services they control, such as search data, language models, and communication delivery. The platform owns its core workflow, business rules, CRM, and application data model.

## Technology Stack

The initial proposed stack is:

| Area | Technology | Purpose |
|---|---|---|
| Frontend | React, TypeScript, Vite | Web application |
| UI | Tailwind CSS, shadcn/ui | Styling and UI components |
| Frontend data | TanStack Query | API state and caching |
| Forms and validation | React Hook Form, Zod | Form handling and validation |
| Backend | NestJS, TypeScript | REST API and application modules |
| API documentation | OpenAPI / Swagger | API contracts and developer documentation |
| Database | PostgreSQL | Persistent relational data |
| ORM and migrations | Prisma | Data access and schema management |
| Background jobs | Redis, BullMQ | Queues, retries, and scheduled work |
| File storage | S3-compatible storage or MinIO | Documents and artifacts |
| AI | Pluggable LLM provider adapter | Model access without provider lock-in |
| Development environment | Docker Compose | Local infrastructure |
| Monorepo | pnpm workspaces, Turborepo | Shared packages and coordinated builds |
| CI | GitHub Actions (proposed) | Automated checks and tests |

This is the proposed stack, not a claim that every component is already configured in the repository. Update this section as implementation decisions are confirmed.

## AI Agents and Background Workers

The platform separates model-assisted reasoning from deterministic application logic.

| Component | Responsibility | LLM required? |
|---|---|---|
| Context processing | Turn company information and documents into structured context and ICP suggestions | Usually |
| Discovery worker | Query sources, normalize results, and store candidates | Usually not |
| Qualification agent | Assess fit against the configured ICP and explain the decision | Usually |
| Enrichment worker | Gather or validate additional business details | Depends on the source and task |
| Outreach agent | Draft personalized messages within configured policies | Usually |
| Reply classifier | Classify replies, such as interested, not interested, asking for pricing, or requesting a meeting | Usually |
| Follow-up scheduler | Schedule next actions and enforce stop conditions | No |
| CRM and analytics services | Persist changes, record activities, and calculate metrics | No |

A workflow orchestrator controls step order, state transitions, retries, and approval gates. The language model does not have unrestricted authority to execute arbitrary actions. Sending messages, updating records, and scheduling follow-ups must pass through validated application services.

## Data and Integrations

### Data Model

The initial domain model is expected to include:

- `users`
- `workspaces`
- `workspace_members`
- `company_profiles`
- `documents`
- `icp_profiles`
- `data_sources`
- `campaigns`
- `leads`
- `contacts`
- `lead_sources`
- `conversations`
- `messages`
- `channel_connections`
- `activities`
- `agent_runs`
- `suppression_entries`
- `usage_records`

The final schema may change as implementation progresses. Workspace ownership should be enforced consistently throughout the API and database access layer.

### Integration Strategy

Integrations are implemented behind internal interfaces so providers can be changed without rewriting the core workflow.

- **Lead sources:** Add one source at a time, starting with a provider that permits the intended use.
- **Email:** Implement one provider end-to-end, including sending, inbound replies, delivery events where available, and connection health.
- **Messaging:** Add WhatsApp, Telegram, or other channels only after verifying the relevant API, account requirements, permissions, and supported operations.
- **LLM:** Start with one provider behind an adapter and retain a provider-independent internal contract.

A public website or a visible phone number does not automatically grant permission to scrape data or automate messages. Each integration must follow its provider's terms and applicable law.

## Security and Responsible Outreach

Security and reliable execution are core requirements, not optional add-ons.

- Enforce workspace-level authorization for every tenant-owned record.
- Store credentials and tokens securely; never commit secrets to source control.
- Encrypt sensitive connection credentials and restrict access to them.
- Validate external inputs and use typed schemas for model outputs and API payloads.
- Record important actions and state transitions in an activity log.
- Use idempotency controls and delivery-state tracking to reduce duplicate actions.
- Respect provider rate limits, opt-outs, suppression lists, and applicable privacy and anti-spam requirements.
- Provide controls to pause campaigns, disable channels, and require human approval.
- Avoid treating model-generated contact details or qualification claims as verified facts without evidence.
- Apply retention and deletion policies to personal and business contact data.

## Development Roadmap

The roadmap below is a proposed implementation sequence.

### Phase 1 — Foundation

- Set up the monorepo, frontend, API, database, Redis, and local Docker environment.
- Implement authentication, workspaces, membership, and authorization.
- Establish shared contracts, migrations, CI, and baseline tests.

### Phase 2 — Business Context

- Build company profile and ICP configuration screens.
- Implement document upload and asynchronous processing.
- Generate editable structured ICP suggestions from company context.

### Phase 3 — Lead Discovery

- Integrate the first permitted lead source.
- Implement search jobs, normalization, deduplication, scoring, and evidence storage.
- Build the leads table and lead detail view.

### Phase 4 — CRM and Email Outreach

- Implement pipeline stages, activities, conversations, and message history.
- Integrate one email provider for outbound messages and inbound replies.
- Add approval gates, follow-up rules, retry policies, and suppression handling.

### Phase 5 — Additional Channels and Analytics

- Add further channel adapters based on verified API capabilities.
- Implement campaign metrics, reply classification, conversion reporting, and outcome tracking.
- Add controlled feedback loops for improving qualification and messaging.

### Phase 6 — Hardening and Release

- Test tenant isolation, permissions, failure recovery, and duplicate prevention.
- Add monitoring, structured logs, backups, and operational alerts.
- Validate provider compliance, usage limits, security controls, and deployment procedures.

## Local Development

The commands below illustrate the expected workflow once the corresponding project files and scripts are implemented. They are not guaranteed to work until the repository setup is complete.

### Prerequisites

- Node.js LTS version compatible with the repository
- pnpm
- Docker and Docker Compose
- Git

### Setup

```bash
git clone <repository-url>
cd b2b-growth-platform

pnpm install
cp .env.example .env

# Start local infrastructure once docker-compose.yml is configured
docker compose up -d

# Run database migrations once Prisma is configured
pnpm db:migrate

# Start development apps once workspace scripts are configured
pnpm dev
```

Configure credentials only in local environment files or a secrets manager. Never commit `.env` files containing real secrets.

## Project Structure

The following is the proposed monorepo layout:

```text
b2b-growth-platform/
├── apps/
│   ├── web/                  # React web application
│   ├── api/                  # NestJS REST API
│   ├── worker-discovery/     # Lead discovery jobs
│   ├── worker-ai/            # Qualification and AI tasks
│   ├── worker-outreach/      # Outbound messages and replies
│   └── worker-documents/     # PDF and Markdown processing
├── packages/
│   ├── database/             # Prisma schema and migrations
│   ├── contracts/            # Shared DTOs and validation schemas
│   ├── agent-core/           # Workflow orchestration
│   ├── ai-provider/           # LLM provider adapters
│   ├── lead-sources/         # Lead discovery adapters
│   ├── messaging/            # Communication channel adapters
│   ├── auth/                 # Shared authorization utilities
│   └── config/               # Shared configuration
├── infra/
│   ├── docker/
│   └── monitoring/
├── docker-compose.yml
├── pnpm-workspace.yaml
└── turbo.json
```

The actual directory layout should be kept aligned with the code as the repository evolves.

## Contributing

1. Create a feature branch from the team's agreed base branch.
2. Keep changes focused and use shared contracts for cross-module communication.
3. Add or update tests for new behavior and failure cases.
4. Run formatting, linting, type checks, and relevant tests before opening a pull request.
5. Document environment variables and integration setup without including secrets.
6. Use pull requests for review and keep module boundaries clear so teammates can work in parallel.

## Project Principles

- **Business-owner friendly:** Complex orchestration should be hidden behind a simple interface.
- **Modular by design:** Providers can be replaced without rewriting the core product.
- **Reliable automation:** Every long-running workflow has explicit state, retries, and recovery behavior.
- **Human control:** Users can review, pause, override, and audit automated actions.
- **Evidence-based qualification:** Lead scores should be explainable and traceable to their sources.
- **Privacy and isolation:** Each workspace's data and credentials must be protected.
- **Incremental delivery:** Prove a complete end-to-end workflow before adding many providers or channels.

---

**B2B Growth Platform** — Discover the right businesses, engage them responsibly, and manage the full lead lifecycle in one place.
