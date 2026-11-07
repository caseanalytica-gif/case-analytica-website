---
name: reflect
description: "Use when the user asks to reflect on the conversation, review it for lasting preferences and reusable workflows, update the project memory with what was learned, or invokes /reflect. Keeps CLAUDE.md and this folder's skills current with the accumulated work on the VIX Risk Model."
---

# Reflect

Copied from the Case Analytica account skill `reflect`, with a section added so
the results land in this project's own memory (`CLAUDE.md`) and skills
(`.claude/skills/`), and the model keeps learning from session to session.

When invoked, review the full current conversation (not prior sessions, unless the user says otherwise) and produce a structured reflection covering:

1. **Lasting preferences and communication style.** Tone, formatting habits, structural preferences (e.g. prioritized bullet lists over prose, how much hedging or caveat language is wanted), level of formality, how the user likes deliverables packaged (chat text vs. file vs. artifact vs. portable export).
2. **Domain and context facts worth remembering.** What the user does, who they work with, recurring subject matter, terminology they use.
3. **Recurring instructions.** Anything said more than once, or said once but clearly meant to apply going forward.
4. **Reusable workflows.** Any multi-step process actually carried out in this conversation that would save the user time if it existed as a named, invokable skill next time. Judge reusability by whether this same sequence of steps would plausibly recur across other future requests from this user, not just this one task.

For this project, also cover:

5. **Model and trading changes.** Rules added, removed or changed in `config.json`; new test results (with sample size, win rate against the normal week, both halves, walk-forward); trades entered or closed in the live record; scheduled tasks created or changed (name, id, time).
6. **What is now out of date.** Anything in `CLAUDE.md` or a skill in `.claude/skills/` that this conversation made wrong.

## Output format

First present findings as a written summary in the chat, grouped under the headings above, in plain language, before proposing anything. Then, for each preference set or reusable workflow judged worth persisting, draft a complete skill (name, one-line description, full SKILL.md body) and call propose_skills with all of them in one call (max 3 per call; if there are more than 3 strong candidates, propose the 3 strongest and name the rest in the text so the user can ask for them explicitly).

## Saving to this project's memory

The project memory is `CLAUDE.md` in this folder. Every session and both
Friday scheduled tasks read it, so it is how the work accumulates.

1. Draft the exact changes to `CLAUDE.md` as before/after text: new facts under
   the section they belong to, corrected rules in the rules table, new live
   trades in the live record, and anything out of date removed or fixed. Keep
   the file short: replace stale lines rather than appending history.
2. If propose_skills is not available, show each new or changed skill as its
   full SKILL.md text in the chat, with the path it would be saved to
   (`.claude/skills/<name>/SKILL.md`).
3. Wait for the user's approval. Then make exactly the approved edits.
4. If this folder is inside the git repo (`portfolio-model/` on branch
   `claude/trusting-curie-8rxokh`), commit only the files you changed, by path,
   and push to that branch. Never push to `main`. If it is the Mac folder
   "Portfolio model ai", save the files there; the user copies them to the repo
   or asks a cloud session to.
5. Follow the writing rules in `CLAUDE.md`: no em dashes and no exclamation points.

## Hard rule

Never write directly to any memory or preference file, and never treat a draft as saved, without the user seeing the exact proposed content first. propose_skills is the correct mechanism for this: it only renders a review card and saves nothing until the user approves it, so calling it satisfies "show me before saving," as long as the proposal shown is the complete, real content and not a placeholder. The same applies to `CLAUDE.md`: show the exact edit, then save only what the user approved.

## When to run

Run this only when the user explicitly asks to reflect, asks what preferences or skills should be saved from the conversation, asks to update the memory with this session's work, or invokes this skill by name. Do not run it automatically at the end of every conversation.
