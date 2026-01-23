#!/usr/bin/env python3
"""
Skill Validation Script
Validates that all skills in .github/skills/ have the correct structure.
"""

import os
import yaml
import sys
from pathlib import Path

def validate_skill(skill_path):
    """Validate a single skill directory."""
    skill_name = os.path.basename(skill_path)

    # Check if SKILL.md exists
    skill_md = os.path.join(skill_path, "SKILL.md")
    if not os.path.exists(skill_md):
        return False, f"{skill_name}: Missing SKILL.md file"

    # Read and check YAML frontmatter
    try:
        with open(skill_md, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for YAML frontmatter
        if not content.startswith('---'):
            return False, f"{skill_name}: Missing YAML frontmatter (should start with '---')"

        # Parse YAML
        parts = content.split('---', 2)
        if len(parts) < 3:
            return False, f"{skill_name}: Invalid YAML frontmatter format"

        frontmatter = parts[1].strip()
        data = yaml.safe_load(frontmatter)

        # Check required fields
        required_fields = ['name', 'description', 'version']
        for field in required_fields:
            if field not in data:
                return False, f"{skill_name}: Missing required field '{field}' in frontmatter"

        # Check that name matches directory
        if data.get('name') != skill_name:
            return False, f"{skill_name}: Frontmatter 'name' ({data.get('name')}) doesn't match directory name"

        return True, f"{skill_name}: OK"

    except yaml.YAMLError as e:
        return False, f"{skill_name}: YAML parsing error: {str(e)}"
    except Exception as e:
        return False, f"{skill_name}: Error: {str(e)}"

def main():
    """Main validation function."""
    skills_dir = Path(".github/skills")

    if not skills_dir.exists():
        print("ERROR: Skills directory not found at .github/skills/")
        sys.exit(1)

    print(f"Validating skills in {skills_dir}")
    print("=" * 60)

    # Get all skill directories
    skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and d.name != 'skills']

    if not skill_dirs:
        print("ERROR: No skill directories found")
        sys.exit(1)

    print(f"Found {len(skill_dirs)} skill directories")
    print()

    # Validate each skill
    all_valid = True
    results = []

    for skill_dir in sorted(skill_dirs):
        is_valid, message = validate_skill(skill_dir)
        results.append((is_valid, message))
        if not is_valid:
            all_valid = False

    # Print results
    for is_valid, message in results:
        status = "✅" if is_valid else "❌"
        print(f"{status} {message}")

    print()
    print("=" * 60)

    # Summary
    valid_count = sum(1 for is_valid, _ in results if is_valid)
    total_count = len(results)

    print(f"Summary: {valid_count}/{total_count} skills valid")

    if all_valid:
        print("🎉 All skills are valid!")
        sys.exit(0)
    else:
        print("⚠️  Some skills have issues. Please fix the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
