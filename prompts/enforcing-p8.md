# Prompt: Enforcing P8 — "Analysis yes, speculation no"

> **Read before authoring any content destined for `wiki/`.**
> P8 is the single strongest trust mechanism in ResearchWiki. Violating it silently poisons the knowledge base.

## The working definition

An LLM agent operating in this workspace may produce:

- **Direct factual claims** grounded in a specific source the agent has seen in this session
- **Observational claims** describing relationships between sources (X cites Y; function A calls function B)
- **Juxtapositions** that surface similarity, difference, or contradiction between sources
- **Structural summaries** of what a source contains

An LLM agent may not produce:

- **Intent claims** about a developer's unstated reasoning
- **Implication claims** about what a paper means beyond what it states
- **Causal claims** about why an experiment succeeded or failed, absent supporting data in the logs
- **Normative claims** about whether a design is good or bad, absent an explicit researcher request

## Concrete tests

Before writing a sentence, ask:

1. **Can I point to the exact source?** If yes, cite it. If no, mark `[speculation]` or remove.
2. **Am I using a hedge verb?** (`seems`, `appears`, `likely`, `probably`, `suggests`, `implies`) — if yes, stop. Either downgrade the sentence to a question or remove it.
3. **Am I assigning a reason that the source does not state?** If yes, stop.
4. **Am I paraphrasing what the source says, or am I extending what the source says?** Paraphrase is fine. Extension is not.

## Ten transformation pairs

These are the most common speculation patterns and their grounded rewrites.

**1.**
- ❌ "The author probably chose this architecture because of performance concerns."
- ✅ "The paper does not state why this architecture was chosen. [speculation about performance motivation removed]"
- ✅ Or: question-form: "Why was this architecture chosen? — Not stated in §3.1. Worth checking the supplementary material."

**2.**
- ❌ "This function seems to be responsible for authentication."
- ✅ "This function is named `loginUser`. It is called from `src/auth/middleware.ts:23`. It writes to the session store. [Purpose beyond these observations not determined.]"

**3.**
- ❌ "The experiment likely failed because of the learning rate."
- ✅ "The experiment produced `NaN` loss at step 340. The logs show learning rate `1e-3` and gradient norm rising monotonically from step 200. [Cause not established.]"

**4.**
- ❌ "The authors are implying a connection to earlier work on attention."
- ✅ "The paper cites [Vaswani2017] in §2 but does not explicitly compare its method to Transformer attention."

**5.**
- ❌ "This design decision seems suboptimal."
- ✅ "The design uses approach A. An alternative approach B is mentioned in [paper-X] as providing better C under condition D. [Whether A or B is better in this context is not evaluated here.]"

**6.**
- ❌ "The code suggests that the author intended to support batching later."
- ✅ "The function signature accepts `List[Tensor]` but all call sites pass a single-element list. [Intent not stated in comments or docs.]"

**7.**
- ❌ "This is probably a bug."
- ✅ "The condition `if x == None` uses `==` rather than `is`. PEP 8 recommends `is` for None comparisons. [Whether this is intentional is not documented.]"

**8.**
- ❌ "The paper obviously generalizes to the multimodal case."
- ✅ "The paper's setup is described for text only (§3.1). Generalization to multimodal inputs is not discussed in the paper."

**9.**
- ❌ "The researcher will want to refactor this soon."
- ✅ *(Do not write this. Normative predictions about the researcher's future actions are not grounded.)*

**10.**
- ❌ "This function is elegant."
- ✅ *(Do not write this. Aesthetic judgment is not grounded.)*

## When the researcher asks for speculation

Sometimes the researcher explicitly wants brainstorming, critique, or speculation. That is fine — but:

1. The speculation happens in the **conversation**, not in the wiki.
2. If the researcher decides to record the speculation in the wiki, it goes into a clearly-labeled block:

   ```
   ## Speculative notes (not grounded in sources)

   *This section contains the researcher's and agent's speculation. It is not a fact claim.*

   - ...
   ```

3. The `authored_by` stays `hybrid` and the page may not be a `type: concept` page — speculative pages should use `type: other`.

## The weekly self-audit prompt

Once per week, the agent running `wiki-lint` should reason through:

> Of the pages I helped author this week, how many contain claims that I could not, right now, point to a source for? For each such claim, was it marked `[speculation]`? If not, that is a P8 violation I introduced. Flag it for researcher review.

This self-audit is part of `wiki-lint`'s speculation check.

## Failure mode: silent drift

The risk is not a single blatant violation. It is **drift** — each week, a handful of plausible-sounding claims slip in without proper grounding. In six months the wiki is 20% LLM speculation, and the researcher has been citing it as if it were fact. This is the scenario P8 exists to prevent.

The lint skill's speculation-ratio metric (default 30%) is the tripwire. But the strongest defense is the agent being honest sentence by sentence.

## One-line summary to remember

> **If you cannot cite it, do not claim it. If you want to claim it, cite it or tag it.**
