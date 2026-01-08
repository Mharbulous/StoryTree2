# Human-in-the-Loop Checkpoint Design

Research consolidated from industry sources on HITL approval workflow patterns.

## Key Design Patterns

### 1. Approval Flows

Pause workflow at pre-determined checkpoint until human reviewer approves or declines. Key characteristics:
- Workflow stops completely at checkpoint
- Human can approve, reject, or modify
- Decision is logged with identity and timestamp

### 2. Confidence-Based Routing

AI defers to human when confidence drops below threshold:
- Define confidence score threshold (research suggests 40%)
- Below threshold → automatic escalation to human
- Above threshold → AI proceeds autonomously

### 3. Return of Control (ROC)

A more nuanced approach enabling users to:
- Modify parameters before action execution
- Provide additional context
- Change the agent's proposed decisions
- Particularly useful in complex scenarios

### 4. Interrupt-Based Patterns

Used in agentic workflows (e.g., LangGraph):
- AI pauses and requests human input
- Human can review, approve, modify, or supply new information
- Workflow resumes with human-provided input

### 5. Feedback as Training Data

Every approval, rejection, or correction becomes training data:
- AI systems learn from human feedback over time
- Performance improves as patterns are learned
- Reduces future escalations for similar scenarios

## When to Involve Humans

| Scenario | Human Involvement |
|----------|-------------------|
| Review tool calls | Approve, edit, or reject before execution |
| Validate outputs | Approve or correct generated content |
| Provide context | Supply missing information or corrections |
| Critical decisions | Pause before high-stakes actions |

## Single Checkpoint Principle

The human checkpoint belongs at the **decision stage**, not scattered throughout.

**Wrong approach:** Multiple small approvals interrupting flow
**Right approach:** Single comprehensive checkpoint when AI exhausts autonomous attempts

## What AI Prepares for Human

Before escalation, prepare:

1. **Structured test output** - JUnit XML or JSON, not raw logs
2. **Fix attempt history** - What was tried with diffs
3. **Confidence scores** - Why escalation happened
4. **Relevant code context** - Around the failure point
5. **Suggested next steps** - Based on debugging attempts

**Key insight:** Synthesize into actionable summaries. Avoid dumping raw logs.

## Checkpoint Question Design

### Bad: Vague Approval Prompts

```
Do you approve this change?
[ ] Yes  [ ] No
```

Problems:
- No specific focus
- Easy to rubber-stamp
- No accountability

### Good: Specific Forcing Questions

```
VALIDATION CHECKPOINT: Story 1.2.3 - "Export to CSV"

Verification passed. Please confirm after demo:

1. Did you see the export complete successfully?      [ ] Yes  [ ] No
2. Does the output file contain expected columns?     [ ] Yes  [ ] No
3. Is the data format acceptable for users?           [ ] Yes  [ ] No
4. Would you ship this to production?                 [ ] Yes  [ ] No

If any "No": What needs to change?
> _______________________________________________
```

Benefits:
- Specific focus per question
- Requires individual acknowledgment
- Structured rejection path
- Clear accountability

## Checklist Size: 5-9 Items

Research suggests:
- Fewer than 5: Too coarse, misses important details
- More than 9: Cognitive overload, leads to skimming
- Sweet spot: 5-7 specific items

Each item should:
- Be independently answerable
- Focus on one observable behavior
- Require explicit yes/no response

## Architecture Considerations

### Event-Driven Checkpoints

```
[AI Completes Work] → [Event: Ready for Validation]
                              ↓
                      [Human Validation Queue]
                              ↓
                      [Human Reviews & Decides]
                              ↓
                      [Event: Approved/Rejected]
                              ↓
                      [Workflow Continues/Reverts]
```

### SLA Considerations

- Define time-to-first-review target
- Define time-to-resolution target
- Prioritize by customer impact, safety impact, deadlines
- Cap work-in-progress to prevent reviewer overload

## Sources

- [Zapier: Human-in-the-loop in AI workflows](https://zapier.com/blog/human-in-the-loop/)
- [Permit.io: HITL for AI Agents Best Practices](https://www.permit.io/blog/human-in-the-loop-for-ai-agents-best-practices-frameworks-use-cases-and-demo)
- [All Days Tech: HITL AI Review Queues](https://alldaystech.com/guides/artificial-intelligence/human-in-the-loop-ai-review-queue-workflows)
- [AWS: Building GenAI workflows with HITL](https://aws.amazon.com/blogs/machine-learning/building-generative-ai-prompt-chaining-workflows-with-human-in-the-loop/)
- [Camunda: What is HITL Automation](https://camunda.com/blog/2024/06/what-is-human-in-the-loop-automation/)
- [LangGraph4j: Implementing Human-in-the-Loop](https://bsorrentino.github.io/bsorrentino/ai/2025/07/13/LangGraph4j-Agent-with-approval.html)
- [AWS: HITL with Amazon Bedrock Agents](https://aws.amazon.com/blogs/machine-learning/implement-human-in-the-loop-confirmation-with-amazon-bedrock-agents/)
- [Microsoft Agent Framework: HITL AI Agents](https://jamiemaguire.net/index.php/2025/12/06/microsoft-agent-framework-implementing-human-in-the-loop-ai-agents/)
- [FlowHunt: HITL Middleware in Python](https://www.flowhunt.io/blog/human-in-the-loop-middleware-python-safe-ai-agents/)
