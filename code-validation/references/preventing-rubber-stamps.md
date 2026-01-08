# Preventing Rubber-Stamp Approvals

Research consolidated from industry sources on forcing functions for meaningful review.

## What is Rubber Stamping?

Rubber stamping occurs when approvals happen without genuine review:
- PRs approved without reading code
- Validation checkpoints clicked through without observation
- Approval given based on trust rather than verification

**Cost:** Issues slip through to production, defeating the purpose of review entirely.

## Why Rubber Stamping Happens

| Cause | Description |
|-------|-------------|
| **No incentive** | Review effort not valued in performance metrics |
| **Trust bias** | Senior author = automatic approval |
| **Time pressure** | Deadline approaching, need to ship |
| **Deference** | "Senior reviewer already approved" |
| **Complexity** | Too hard to understand, easier to approve |
| **Fatigue** | Reviewer overload leads to shortcuts |

## Detection Signals

| Signal | Indicates |
|--------|-----------|
| Very short approval time | Didn't actually review |
| No comments or questions | No engagement with content |
| Approval follows senior approval | Deference, not review |
| Pattern of all-approvals | No critical thinking |
| No rejection path usage | Too easy to say yes |

## Prevention Strategies

### 1. Specific Questions, Not Vague Approval

**Wrong:**
```
Approve this change? [Yes] [No]
```

**Right:**
```
1. Did you observe the export complete?  [Yes] [No]
2. Does output match expected format?    [Yes] [No]
3. Would you ship this to users?         [Yes] [No]

If any No, describe issue: ___________
```

### 2. Individual Acknowledgment

Each checkpoint item requires explicit response. No global "approve all" button.

Research from consolidated workflow design:
> "Each item requires individual acknowledgment, not global checkbox."

### 3. Variable Presentation

Highlight different elements each time to prevent pattern-based approval:
- Randomize question order
- Vary highlighted evidence
- Change presentation format periodically

### 4. Accountability Logging

Record with decision:
- **Who** validated
- **When** they validated
- **How long** they spent
- **What** they observed

This creates accountability—post-issues can be traced back to validator.

### 5. Easy Rejection Path

Make it simple to say "no":
- Structured feedback field
- Pre-defined rejection reasons
- No penalty for legitimate rejection

If rejection is hard, approval becomes default.

### 6. Eyeball Time Metrics

Meta uses "eyeball time" to measure actual time spent analyzing:
- Track time from opening to decision
- Flag suspiciously short review times (under 30 seconds)
- Use as coaching signal, not punishment
- Result: Most PRs now reviewed within hours with quality

### 7. Culture and Coaching

**Celebrate thorough reviews:**
- Highlight good review examples in standups
- Include review quality in performance discussions
- Coach individuals who show rubber-stamp patterns one-on-one
- Get to the root cause—intimidation, confusion, or time pressure

**Deconstruct good examples:**
- Show what thorough validation looks like
- Discuss why specific questions matter
- Practice with sample scenarios

### 8. Quality Control Testing

A senior team member could develop a habit of creating occasional rule-breaking submissions as a quality-control penetration test:
- Helps change culture where questioning seniors is uncomfortable
- Verifies checkpoint actually catches problems
- Creates learning opportunities when issues are caught

### 9. Right-Size the Checkpoint

**Too many items:** Leads to skimming
**Too few items:** Misses important checks
**Right size:** 5-9 specific, observable items

Each item should take ~10 seconds to genuinely verify.

## Forcing Functions Summary

| Technique | Effect |
|-----------|--------|
| Specific questions | Can't approve without understanding |
| Individual acknowledgment | Each item requires attention |
| Rejection path | Makes "no" a valid option |
| Time tracking | Surfaces too-fast approvals |
| Identity logging | Creates accountability |
| Variable presentation | Prevents pattern matching |

## Implementation in Validation Skill

The `human-validation` skill implements:

1. **Demo script** - Human must follow steps to observe
2. **Specific questions** - 3-5 observable criteria
3. **Individual responses** - Each question requires answer
4. **Notes field** - Easy to explain rejection
5. **Identity capture** - Who validated, when
6. **Decision record** - Logged for accountability

## Sources

- [Medium: You can stop the Rubber Stamping](https://sunislife.medium.com/you-can-stop-the-rubber-stamping-ee8d41ec669a)
- [LinkedIn: Reviewing the Code Reviewer](https://www.linkedin.com/pulse/reviewing-code-reviewer-avoiding-rubber-stamp-prs-paul-klingman)
- [Amy: Death to the rubber stamp!](http://mathamy.com/death-to-the-rubber-stamp.html)
- [SSW Rules: Rubber stamp PRs](https://www.ssw.com.au/rules/rubber-stamp-prs/)
- [Bitband: Dangers of Rubber Stamping](https://www.bitband.com/blog/the-dangers-of-rubber-stamping-a-git-push-request/)
- [Core Security: Rubber Stamping Cybersecurity Concern](https://www.coresecurity.com/blog/what-rubber-stamping-and-why-it-serious-cybersecurity-concern)
- [Chromium: Mandatory Code-Review and Native OWNERS](https://chromium.googlesource.com/chromium/src/+/main/docs/code_review_owners.md)
- [Kodus: Impact of Code Review on Workflow](https://kodus.io/en/the-impact-of-code-review/)
- [Our Code World: Code Review Best Practices](https://ourcodeworld.com/articles/read/2372/code-review-best-practices-for-better-software-quality)
