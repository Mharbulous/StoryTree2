# Human Decision Workflow

When a handover requires human decision-making with subagent recommendations.

## MANDATORY CHECKLIST - Complete Before Responding

Before you respond to the human, verify you have ALL of these:

- [ ] **Executive summary**: Explained what the content DOES (not just "TimeCamp references")
- [ ] **Why misplaced**: Explained why current location is wrong
- [ ] **Impact statement**: What each option means for manual usability
- [ ] **YOUR recommendation**: Either counter-recommend OR explicitly agree with YOUR reasoning
- [ ] **Your justification**: YOUR independent analysis (not restating subagent)

**If ANY box is unchecked, your response is incomplete. Do not send it.**

## The Iron Rule

```
YOU MUST add your own recommendation. Relaying is failure.
```

Presenting options without YOUR recommendation = failing this skill.
Presenting subagent's recommendation without YOUR analysis = failing this skill.
Saying "Subagent recommends X" and asking "which do you prefer?" = failing this skill.

## The Counter-Recommendation Requirement

When a subagent provides a recommendation, you have exactly TWO valid responses:

### Option 1: Counter-Recommend (Preferred)
If you can identify an equally good alternative:
- State the subagent's recommendation
- State YOUR counter-recommendation
- Justify persuasively why yours is equally valid
- Let the human choose between two reasoned positions

### Option 2: Explicit Agreement (Only If No Alternative)
If no equally good alternative exists:
- State the subagent's recommendation
- Explicitly say "I agree with this recommendation"
- Give YOUR OWN independent reasoning (not just restating theirs)
- Explain what alternatives you considered and why they're inferior

**What you CANNOT do:**
- Present options and just ask "which do you prefer?" (no recommendation)
- Present subagent's recommendation without your own analysis
- Say "the subagent recommends X" and move on
- Give a weak "I agree" without your own justification

## FAILING vs PASSING Examples

### FAILING Response (Do NOT do this)
```
The subagent analyzed the options:
- Option A: Merge content
- Option B: New section
Subagent recommends Option A because consolidation reduces navigation.
Which option do you prefer?
```
**Why this fails**: No executive summary. No YOUR recommendation. Just relaying.

### PASSING Response (Do THIS)
```
## Context Summary
The Document Filing chapter contains step-by-step instructions for logging
time in TimeCamp when filing documents. These teach users how to select
activity codes, choose categories, and link time entries to specific files.

This content belongs in Chapter 09 (Time Tracking) because a legal assistant
looking for "how do I log my time?" would look there, not in Document Filing.

## Options
[options with pros/cons]

## Recommendations
The subagent recommends Option A because [their reasoning].

I recommend Option B because [YOUR independent analysis]. The content we're
moving is procedural, while "Time Entry Basics" is conceptual. Mixing these
makes the section hard to scan.

Which option would you like?
```
**Why this passes**: Executive summary explains what content does. YOUR recommendation with YOUR reasoning.

### Main Agent Response Format

**When counter-recommending:**
```
The subagent recommends [Option X] because [their reasoning].

However, I recommend [Option Y] because [your reasoning].
This alternative is equally strong because [specific justification].
```

**When agreeing:**
```
The subagent recommends [Option X] because [their reasoning].

I agree with this recommendation because [your independent reasoning].
I considered [Alternative Y] but [why it's not equally good].
```

### Common Rationalizations (All Wrong)

| Excuse | Reality |
|--------|---------|
| "The subagent already did the analysis" | Your job is independent evaluation, not relay. |
| "I agree so I'll just present their recommendation" | Agreement must be explicit with YOUR reasoning. |
| "Counter-recommending might confuse the human" | Two perspectives help humans decide. That's the point. |
| "I don't have a better alternative" | Then say so explicitly with justification. |
| "I presented both options, that's enough" | Options without YOUR recommendation = failure. |
| "The subagent's reasoning was complete" | Your reasoning must be INDEPENDENT, not endorsement. |
| "I added context, isn't that enough?" | Context + relay = still relay. Add YOUR recommendation. |

## The Executive Summary Requirement

```
ASSUME the human has NOT read the handover or referenced documents.
ASSUME the human does not remember what this content does or why it matters.
```

The human is busy. They haven't read the handover. They don't remember the details. Your job is to give them everything they need to make a good decision in ONE place.

Before presenting any choice that requires human decision:

1. **Read the actual content** being discussed (not just the handover description)
2. **Synthesize what it does** and why it matters (not just "TimeCamp references")
3. **Explain why the decision matters** - what's the impact of each choice?
4. **Present all context BEFORE the options**

### Executive Summary Format

```
## Context Summary

[1-3 sentences on what this task is about]

**What we're deciding**: [the specific decision needed]

**Key facts**:
- [Relevant fact from handover or key files]
- [Another relevant fact]
- [Impact or consequence of this decision]

## Options

[Now present the options with recommendations]
```

### What Context to Include

| MUST Include | Can Exclude |
|--------------|-------------|
| What the content actually says (summarize it) | Exact file paths (unless human asked) |
| Why it's currently in the wrong place | Technical implementation details |
| What each option means for the user of the manual | History of how we got here |
| Which chapters/sections are involved and why | Obvious information |
| Impact of each choice on manual usability | |

### Red Flags - You're About to Fail

- "TimeCamp references" without explaining what those references teach
- "Content in wrong chapter" without explaining what the content does
- Jumping straight to options without context
- Saying "as described in the handover" (they haven't read it!)

### Common Rationalizations (All Wrong)

| Excuse | Reality |
|--------|---------|
| "The handover file has all the context" | Human hasn't read it. Summarize. |
| "I'll link to the relevant section" | Links require clicks. Summarize inline. |
| "The human knows this project" | Never assume. Fresh context every decision. |
| "Summary would be too long" | Then prioritize ruthlessly. Key facts only. |
| "I described the options clearly" | Options without context = meaningless choice. |
| "The item title explains it" | "TimeCamp references" tells them nothing useful. |

## Putting It Together

When presenting a human decision:

1. **Executive summary** (assume no prior context)
2. **Subagent recommendation** with their justification
3. **Your counter-recommendation OR agreement** with your justification
4. **Clear question** asking for the human's choice

### Example (Counter-Recommending)

```
## Context Summary

The Document Filing chapter (03) currently contains instructions for logging
time in TimeCamp when filing documents. These sections teach:
- How to select the correct activity code when filing court documents
- When to use "Administrative" vs "Legal Work" categories
- How to add notes linking time entries to specific files

**Why this is misplaced**: A legal assistant looking for time tracking guidance
would look in Chapter 09 (Time Tracking), not Document Filing.

**What we're deciding**: Where to move this content - merge into existing section
or create a new section?

**Key facts**:
- The content is procedural (~40 lines of step-by-step instructions)
- Chapter 09 has a conceptual "Time Entry Basics" section (what TimeCamp is,
  why we use it)
- These instructions are distinct from basics - they're specific workflows

## Options

**Option A: Merge into "Time Entry Basics"**
- Pros: All TimeCamp content in one place
- Cons: Mixes concepts and procedures, section becomes 80+ lines

**Option B: New section "TimeCamp Activity Logging"**
- Pros: Clear separation of "what is this" vs "how to do it"
- Cons: Two sections to navigate instead of one

## Recommendations

The subagent recommends Option A because consolidation reduces navigation
and avoids redundancy.

I recommend Option B. The content we're moving is procedural step-by-step
instructions, while "Time Entry Basics" is conceptual background. Mixing
these creates a section that's hard to scan - users looking for "how do I
log filing time?" must wade through "what is TimeCamp?" first. A separate
procedures section lets users skip to what they need.

**Which option would you like?**
```

### Example (Agreeing)

```
## Recommendations

The subagent recommends Option A because [their reasoning].

I agree with Option A. My independent reasoning: [your own analysis that
leads to the same conclusion]. I considered Option B but it's inferior
because [specific reason].

**Proceed with Option A?**
```
