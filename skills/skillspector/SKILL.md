# SkillSpector Skill

## Overview
SkillSpector is a security scanner for AI agent skills. It can analyze a skill directory, SKILL.md file, zip archive, or Git repository and produce a risk assessment (score, severity, recommendation) along with detailed findings.

## Installation
You can install SkillSpector as a standalone tool using **uv** (preferred) or **pip**:

```bash
# Preferred – using uv (install without cloning)
uv tool install git+https://github.com/NVIDIA/skillspector.git

# Or using pip
pip install git+https://github.com/NVIDIA/skillspector.git
```

If you need to develop or run tests, clone the repository into a temporary location and install the development dependencies:

```bash
git clone https://github.com/NVIDIA/skillspector.git temp_skills_repo/SkillSpector
cd temp_skills_repo/SkillSpector
uv venv .venv && source .venv/bin/activate   # or python -m venv .venv && source .venv/bin/activate
make install-dev
```

## Usage
The command line interface provides several convenient sub‑commands:

```bash
# Scan a local skill directory
skillspector scan ./my-skill/

# Scan a single SKILL.md file
skillspector scan ./SKILL.md

# Scan a remote Git repository
skillspector scan https://github.com/user/my-skill

# Scan a zip archive
skillspector scan ./my-skill.zip
```

### Output formats
- **Terminal** (default, pretty printed) – `skillspector scan ./my-skill/`
- **JSON** – `skillspector scan ./my-skill/ --format json --output report.json`
- **Markdown** – `--format markdown`
- **SARIF** – `--format sarif`

### Baseline / false‑positive suppression
To ignore known findings you can generate a baseline:

```bash
skillspector baseline ./my-skill/ -o .skillspector-baseline.yaml
# Subsequent scans will only report NEW findings
skillspector scan ./my-skill/ --baseline .skillspector-baseline.yaml
```

## Integration with Gekyume
You can invoke SkillSpector from other skills or from the agent via the **`run_command`** tool. Example command:

```bash
skillspector scan ./path/to/skill/ --format json --no-llm
```

The JSON report contains the fields:
- `risk_assessment.score`
- `risk_assessment.severity`
- `risk_assessment.recommendation`
- `issues` (list of findings with IDs, categories, severity, confidence)

Use these values to gate skill installation in CI pipelines or at runtime.

## Permissions
Running SkillSpector requires:
- **command** permission for `skillspector` (installed binary) and `git` (if cloning).
- **read_file** permission for the skill directory you are scanning.
- **write_file** permission for any output file you specify with `--output`.
- **execute_url** permission for `api.osv.dev` (live vulnerability lookups).

## References
- Repository: https://github.com/NVIDIA/SkillSpector
- Documentation: `docs/` directory in the repo
- License: Apache 2.0
