# Test Evidence Collection for Human Review

*Research Date: December 2025*

## Overview

Evidence collection involves gathering and documenting proof that software meets requirements. For story verification, we collect evidence that acceptance criteria are satisfied, enabling human reviewers to make informed decisions.

## Why Collect Evidence?

- **Prove compliance** at any moment
- **Complete audit trail** for review
- **Accountability** - who tested what, when
- **Transparency** - clear record of verification activities
- **Efficiency** - no re-testing for audits

## Types of Evidence

### For Software Verification

| Evidence Type | Description | Example |
|---------------|-------------|---------|
| **Test Results** | Automated test pass/fail | pytest output showing all tests pass |
| **Code Locations** | Where feature is implemented | `src/exporter.py:45-80` |
| **Execution Logs** | Runtime behavior proof | Application logs during test run |
| **Screenshots/Artifacts** | Visual proof | Screenshot of export dialog |
| **Configuration State** | Settings during test | config.json snapshot |

### For Acceptance Criteria

| Criterion Type | Evidence Needed |
|----------------|-----------------|
| Functional | Test demonstrates behavior works |
| Data-related | Output contains expected data |
| Integration | Cross-component test passes |
| Performance | Metrics meet threshold |
| Security | No vulnerabilities detected |

## Evidence Storage Structure

```
${STORYTREE_DATA_DIR}/evidence/{story_id}/
├── summary.json          # Verification summary
│   ├── story_id
│   ├── verified_at
│   ├── result (pass/fail)
│   └── criteria_status
├── criteria/             # Per-criterion evidence
│   ├── criterion_1/
│   │   ├── test_output.txt
│   │   └── code_refs.json
│   └── criterion_2/
├── logs/                 # Test execution logs
│   ├── pytest_output.txt
│   └── execution.log
└── artifacts/            # Generated outputs
    ├── exports/
    └── screenshots/
```

## Evidence Format Standards

### Summary Document

```json
{
  "story_id": "1.7",
  "story_title": "Privacy & Data Security",
  "verified_at": "2025-12-29T10:30:00Z",
  "verified_by": "automated",
  "result": "pass",
  "criteria": [
    {
      "index": 1,
      "text": "All data stored locally with no network transmission",
      "status": "pass",
      "evidence": {
        "tests": ["tests/test_database.py::test_no_network_calls"],
        "code": ["src/database.py:45-60"],
        "notes": "Verified no outbound network connections during operation"
      }
    }
  ],
  "test_suite": {
    "total": 42,
    "passed": 42,
    "failed": 0,
    "skipped": 0
  }
}
```

### Per-Criterion Evidence

```json
{
  "criterion": "User can export activities as CSV",
  "status": "pass",
  "evidence": {
    "test_file": "tests/test_exporter.py",
    "test_function": "test_csv_export",
    "test_output": "PASSED in 0.5s",
    "code_file": "src/syncopaid/exporter.py",
    "code_lines": "45-80",
    "artifacts": [
      "evidence/1.3/artifacts/sample_export.csv"
    ]
  },
  "collected_at": "2025-12-29T10:30:00Z"
}
```

## Professional Standards (IIA 2330)

The Institute of Internal Auditors Standard 2330 states:

> "Internal auditors must document sufficient, reliable, relevant, and useful information to support the engagement results and conclusions."

### Applied to Code Verification

| Standard | Application |
|----------|-------------|
| **Sufficient** | Enough evidence to prove criterion met |
| **Reliable** | From automated, repeatable tests |
| **Relevant** | Directly relates to acceptance criterion |
| **Useful** | Helps human reviewer make decision |

## Automation Best Practices

### 1. Automated Collection

```python
def collect_evidence(criterion, test_result, code_refs):
    """Automatically collect and store evidence."""
    evidence = {
        "criterion": criterion,
        "status": "pass" if test_result.passed else "fail",
        "test_output": test_result.output,
        "code_refs": code_refs,
        "collected_at": datetime.now().isoformat()
    }
    save_evidence(story_id, criterion.index, evidence)
```

### 2. Timestamps Everything

Every piece of evidence should include:
- When collected
- What version of code
- What test configuration
- Who/what triggered collection

### 3. Centralized Repository

Store all evidence in one location:
- Easy retrieval during review
- Complete audit trail
- Consistent format

### 4. Audit Trail

Maintain log of:
- All tests executed
- All evidence collected
- Any manual overrides
- Human decisions made

## Common Pitfalls

1. **Missing timestamps** - Can't prove when testing occurred
2. **Incomplete evidence** - Not enough to justify decision
3. **Scattered storage** - Evidence in multiple places
4. **Format inconsistency** - Hard to aggregate/report
5. **No accountability** - Can't trace who verified what

## Sources

- [Optimizing Testing and Evidence Collection | AuditBoard](https://auditboard.com/blog/optimizing-testing-and-evidence-collection-with-technology)
- [Automated Evidence Collection for Compliance | Secureframe](https://secureframe.com/blog/automated-evidence-collection)
- [How to Automate Evidence Collection | CyberSierra](https://cybersierra.co/blog/automate-evidence-collection-compliance/)
- [Evidence Collection Guide | Sprinto](https://sprinto.com/facts/compliance/evidence-collection-guide/)
