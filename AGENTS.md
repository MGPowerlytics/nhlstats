# AGENTS

- PostgreSQL is the primary runtime system of record for operational data.
- Prefer immutable, reproducible runtime artifacts over mutable bind-mounted runtime behavior.
- Keep a single canonical schema definition and governed migration path; conflicting DDL owners are not acceptable.
