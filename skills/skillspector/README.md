# SkillSpector

A security scanner for AI agent skills. It analyses a skill's files, detects vulnerable patterns, and generates a risk assessment (score, severity, recommendation).

## Installation
```bash
# Preferred method using uv (install globally as a tool)
uv tool install git+https://github.com/NVIDIA/skillspector.git

# Or with pip
pip install git+https://github.com/NVIDIA/skillspector.git
```

## Quick usage
```bash
# Scan a local skill directory
skillspector scan ./my-skill/

# Scan a single SKILL.md file
skillspector scan ./SKILL.md

# Scan a remote repo
skillspector scan https://github.com/user/my-skill
```

### Output formats
- **Terminal** (default) – `skillspector scan ./my-skill/`
- **JSON** – `--format json --output report.json`
- **Markdown** – `--format markdown`
- **SARIF** – `--format sarif`

## Baseline handling (false‑positive suppression)
```bash
# Generate a baseline of current findings
skillspector baseline ./my-skill/ -o .skillspector-baseline.yaml

# Subsequent scans only report new findings
skillspector scan ./my-skill/ --baseline .skillspector-baseline.yaml
```

## Permissions required
- `command` permission for `skillspector` (and `git` if cloning a repo)
- `read_file` permission for the skill directory being scanned
- `write_file` permission for any `--output` file
- `execute_url` permission for `api.osv.dev` (live vulnerability lookups)

## Integration with Gekyume
Invoke from other skills or directly via the `run_command` tool, for example:
```bash
skillspector scan ./path/to/skill/ --format json --no-llm
```
The JSON report contains `risk_assessment` fields and a list of `issues` you can use to gate skill installation.

---
**Repository:** https://github.com/NVIDIA/skillspector
**License:** Apache 2.0
