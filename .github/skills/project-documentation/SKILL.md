---
name: project-documentation
description: Guidelines for creating and maintaining a high-fidelity documentation ecosystem that serves as the single source of truth for developers, stakeholders, and AI agents.
version: 1.0.0
---

# Writing & Maintaining Project Documentation

## 🎯 Purpose
To create a high-fidelity documentation ecosystem that serves as the "single source of truth" for developers, stakeholders, and AI agents. The goal is to maximize clarity and minimize the "Time to First Commit" for new contributors.

## 📚 The Documentation Hierarchy
A project's health is measured by the accessibility of its information. Use the following structure:

- **README.md (The Map)**: The entry point. Tells you what the project is, how to install it, and how to run it.
- **ADRs (The History)**: Architecture Decision Records. Documents the *why* behind significant technical choices.
- **Technical Docs (The Blueprint)**: Deep dives into system architecture, data flows, and API specifications.
- **SOPs/Skills (The How-To)**: Step-by-step guides for specific tasks (like this file).
- **Inline Docs (The Details)**: Docstrings and comments within the code for function-level context.

## ✍️ Writing Standards

### 1. The "Readability First" Rule
- **Use Active Voice**: "The function calculates the total," not "The total is calculated by the function."
- **Be Concise**: Use bullet points and headers to break up walls of text.
- **No Jargon Without Context**: Define project-specific acronyms upon first use.

### 2. Formatting & Visuals
- **Markdown Mastery**: Use code blocks for commands, bold text for UI elements, and tables for configuration parameters.
- **Diagrams as Code**: Use Mermaid.js or similar tools to embed diagrams. This allows version control to track changes in architecture visually.

## 🔄 Maintenance & Anti-Rot Strategy

### 1. The "Doc-as-Code" Workflow
- **PR Requirement**: If a Pull Request changes a feature, the documentation *must* be updated in the same PR.
- **Versioned Docs**: Ensure documentation matches the current version of the software (especially for APIs).

### 2. Automated Validation
- **Link Checking**: Use CI/CD tools (like `markdown-link-check`) to ensure no external links or internal references are broken.
- **Snippet Testing**: Whenever possible, use tools that test code snippets inside documentation to ensure they actually run.

## 🧹 Documentation Cleanup Checklist
- [ ] **Stale Content**: Remove instructions for deprecated features.
- [ ] **Searchability**: Ensure the README has a Table of Contents if it exceeds two scrolls.
- [ ] **Onboarding Test**: Can a new developer get the project running using only the README?
- [ ] **ADR Completion**: Is every major architectural change accompanied by an ADR?

## 🏷️ ADR Template (Quick Reference)
When creating a new Architecture Decision Record, include:

- **Title**: Concise name of the decision.
- **Status**: Proposed / Accepted / Superseded.
- **Context**: What is the problem we are solving?
- **Decision**: What are we doing?
- **Consequences**: What are the trade-offs (positive and negative)?
