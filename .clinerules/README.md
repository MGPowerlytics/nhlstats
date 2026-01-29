# .clinerules/ - Project Knowledge Base for AI Assistants

This directory contains structured documentation about the Multi-Sport Betting System, designed specifically for AI assistants (GitHub Copilot, Cline, etc.) to understand the project architecture, data model, and development patterns.

## Purpose

- Provide AI assistants with comprehensive project knowledge to answer questions accurately
- Reduce duplication of information across different documentation files
- Create a single source of truth for project architecture and conventions
- Enable AI assistants to understand context when making code suggestions

## File Structure

| File | Description |
|------|-------------|
| `01_project_architecture.md` | High-level system overview, component relationships, technology stack |
| `02_data_model.md` | Database schema, table relationships, data flow, key tables |
| `03_elo_system.md` | Unified Elo interface, sport-specific implementations, parameters, usage |
| `04_betting_pipeline.md` | DAG workflow, edge calculation, Kalshi integration, betting logic |
| `05_development_guidelines.md` | Coding conventions, testing procedures, deployment, CI/CD |
| `06_common_tasks.md` | How to add new sports, modify parameters, troubleshoot, common operations |

## How to Use

1. **For AI Assistants**: Reference these files when answering questions about the project
2. **For Developers**: Use as a quick reference for project architecture and conventions
3. **For Onboarding**: New team members can read these files to understand the system

## Relationship to Other Documentation

- `.github/copilot-instructions.md` - Contains high-level instructions and references these files
- `docs/` directory - Contains detailed human-oriented documentation
- `README.md` - Project overview and getting started guide

## Maintenance

- Keep these files updated when making significant architectural changes
- Ensure consistency with actual code and configuration
- Add new files as needed for additional project areas
- Review periodically for accuracy and completeness

## Examples of AI Assistant Queries

- "How does the Elo system work in this project?"
- "What's the database schema for betting recommendations?"
- "How do I add a new sport to the system?"
- "What are the coding conventions for this project?"
- "How does the DAG workflow operate?"

Each query should be answerable by referencing the appropriate .clinerules/ file.

---

*Last Updated: 2026-01-26*
