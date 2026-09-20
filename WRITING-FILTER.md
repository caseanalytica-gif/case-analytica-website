# Writing filter

Run this over any draft before it ships: an article, a social post, an email, a video script.

This file lives in the Website repo on purpose. The cloud routine that drafts social copy has a
git checkout of this repo but cannot reach `Dea_AI_Patterns_To_Avoid.md` in the CA AI folder, so
the rules it needs are here. The full filter, with Dea's own examples, is still that file, and it
outranks this one wherever they differ.

## Two hard rules, zero tolerance

- **No em dashes.** Anywhere. Including section labels in a script.
- **No exclamation points.** Anywhere outside a URL or code.

```bash
grep -n '—' <file>
grep -n '!' <file>
```

## The patterns to grep for, one at a time

Do not eyeball this. A site-wide scan on 2026-09-20 found seven instances of a banned
construction that a looser "check for bad patterns" instruction had let through.

**1. Negative parallelism.** The one that actually slips through.

```bash
grep -niE "isn'?t just|is not just|not just [a-z']+,? but|it'?s not a [a-z]+, it'?s" <file>
```

Rewrite so the sentence asserts the thing instead of seesawing between a denial and a
correction. "Every extra day past a deadline is a legal problem and a real cost" rather than
"isn't just a legal problem, it's a real cost."

**2. Vague attribution.** A claim sourced to a category instead of a name.

```bash
grep -niE "experts (say|argue|agree)|studies show|research suggests|observers|industry reports|many believe|it is widely" <file>
```

Name the source and link it, or say plainly whose estimate it is. Never manufacture a citation
to fill the gap.

**3. Promotional and significance inflation.**

```bash
grep -niE "stands as a testament|plays a (vital|crucial|key) role|pivotal|groundbreaking|vibrant|underscore|a key turning point|represents a significant" <file>
```

State the fact and let the reader weigh it.

**4. AI vocabulary.**

```bash
grep -niE "\bdelve|\bcrucial\b|\btapestry\b|\bintricate\b|\bmultifaceted\b|\brobust\b|\bfoster\b|\brealm\b|^(Additionally|Moreover|Furthermore)," <file>
```

**5. Participial tails.** A clause bolted on to manufacture insight.

```bash
grep -niE ", (highlighting|emphasi[sz]ing|underscoring|contributing to|reflecting|showcasing)" <file>
```

Cut the tail. If the point matters, give it its own sentence.

**6. Copula avoidance.** Machine prose avoids "is."

```bash
grep -niE "serves as|functions as|stands as" <file>
```

**7. Tidy endings.**

```bash
grep -niE "In conclusion|^Ultimately,|Looking ahead|Despite its" <file>
```

End on a concrete next step, never a summary.

## Also cut

Manufactured triads used for rhythm. Perfectly symmetrical sentences. Drumbeat repetition of one
anchor phrase. Sanitized euphemism like "justice-involved individuals" in place of the actual
program, number or person. Passive voice that hides who acted: name the DA, the attorney, the
Board. Openers that state the obvious before arriving ("In today's...", "When it comes to..."):
open with a specific instead. Overhedged sign-offs like "I hope this helps" or "feel free to
reach out."

## What NOT to strip

**Leave "actually" alone.** It is the site's signature and it marks the gap between what people
are told and what is true. It belongs in headings and in prose. Same for "leverage" as a noun
about plea pressure, which is a real subject here rather than filler.

**Never soften a position to make prose sound more natural.** A hedged version of the core
message is a hard failure, not a style choice. Remove the tells, keep the spine. An edit that
reads more smoothly while claiming less is a worse draft.

**Never add a fact to smooth a sentence.** No statistic, date, dollar figure or case outcome
gets introduced by an editing pass. If a claim needs a source, flag it.
