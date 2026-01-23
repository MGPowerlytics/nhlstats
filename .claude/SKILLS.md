# Skills Index

This document provides a categorized index of all available skills for the NHL Stats project.

## Overview
- **Total Skills**: 15
- **Last Updated**: 2026-01-23
- **Location**: `.github/skills/` (accessible via `.claude/skills/` symbolic link)

## Skills by Category

### 🏗️ Development & Architecture
- **database-design** - Data modeling and design guidelines
- **database-operations** - Database maintenance and operations
- **test-driven-development** - TDD practices and patterns
- **testing-patterns** - Testing strategies and methodologies
- **repository-organization** - Codebase structure and organization

### ☁️ Infrastructure & Operations
- **airflow-3x-migration** - Airflow 2.x to 3.x migration guidance
- **airflow-dag-patterns** - Airflow DAG design patterns
- **extreme-persistence** - Data persistence strategies
- **troubleshooting** - Debugging and issue resolution

### 🎯 Business & Strategy
- **betting-strategy** - Sports betting strategies and analysis
- **strategic-thinking** - Project planning and strategic decision making
- **kalshi-api-integration** - Kalshi prediction market integration

### 📚 Documentation & Processes
- **project-documentation** - Documentation standards and practices
- **adding-new-sport** - Process for adding new sports to the system

### 📊 Analytics & Models
- **elo-rating-systems** - Elo rating system implementation and theory

## Skill Details

### adding-new-sport
- **Location**: `.github/skills/adding-new-sport/SKILL.md`
- **Access**: `.claude/skills/adding-new-sport/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### airflow-3x-migration
- **Location**: `.github/skills/airflow-3x-migration/SKILL.md`
- **Access**: `.claude/skills/airflow-3x-migration/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### airflow-dag-patterns
- **Location**: `.github/skills/airflow-dag-patterns/SKILL.md`
- **Access**: `.claude/skills/airflow-dag-patterns/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### betting-strategy
- **Location**: `.github/skills/betting-strategy/SKILL.md`
- **Access**: `.claude/skills/betting-strategy/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### database-design
- **Location**: `.github/skills/database-design/SKILL.md`
- **Access**: `.claude/skills/database-design/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### database-operations
- **Location**: `.github/skills/database-operations/SKILL.md`
- **Access**: `.claude/skills/database-operations/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### elo-rating-systems
- **Location**: `.github/skills/elo-rating-systems/SKILL.md`
- **Access**: `.claude/skills/elo-rating-systems/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### extreme-persistence
- **Location**: `.github/skills/extreme-persistence/SKILL.md`
- **Access**: `.claude/skills/extreme-persistence/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### kalshi-api-integration
- **Location**: `.github/skills/kalshi-api-integration/SKILL.md`
- **Access**: `.claude/skills/kalshi-api-integration/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### project-documentation
- **Location**: `.github/skills/project-documentation/SKILL.md`
- **Access**: `.claude/skills/project-documentation/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### repository-organization
- **Location**: `.github/skills/repository-organization/SKILL.md`
- **Access**: `.claude/skills/repository-organization/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### strategic-thinking
- **Location**: `.github/skills/strategic-thinking/SKILL.md`
- **Access**: `.claude/skills/strategic-thinking/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### test-driven-development
- **Location**: `.github/skills/test-driven-development/SKILL.md`
- **Access**: `.claude/skills/test-driven-development/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### testing-patterns
- **Location**: `.github/skills/testing-patterns/SKILL.md`
- **Access**: `.claude/skills/testing-patterns/SKILL.md`
- **Description**: *See individual SKILL.md file for details*

### troubleshooting
- **Location**: `.github/skills/troubleshooting/SKILL.md`
- **Access**: `.claude/skills/troubleshooting/SKILL.md`
- **Description**: *See individual SKILL.md file for details*


## Usage

Skills are automatically available to Claude when working on this project. The symbolic link at `.claude/skills` points to the actual skills directory at `.github/skills`.

## Adding New Skills

1. Create a new directory in `.github/skills/[skill-name]/`
2. Create `SKILL.md` file with YAML frontmatter and content
3. Update this index with the new skill
4. Test accessibility via `.claude/skills/[skill-name]/SKILL.md`

## Validation

Run the validation script to ensure all skills follow the correct format:
```bash
python scripts/validate_skills.py
```

---

*Generated: 2026-01-23*
*Total Skills: 15*
