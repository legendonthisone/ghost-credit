# Ghost Credit build log (Kiroween 2026)

One entry per build day. This log feeds the Kiro write-up and the blog post.

## Day 0, Mon 16 Nov 2026

What I did
- Requested the Kiroween Kiro credits.
- Ran one Kiro test prompt to confirm the AI models work from Nigeria.
- Created this public repo with the MIT licence.
- Set git to my GitHub noreply email.
- Added 4 steering docs in .kiro/steering: product, tech, payments-nigeria, boundaries.

Kiro features used today
- Steering docs: they give Kiro the product rules, tech rules, Nigerian payment knowledge and hard boundaries before any spec is written.

Why steering first
- Kiro reads these on every request, so the rules (money in kobo, rules decide and AI explains, no Shield code, no secrets) shape every spec and every line of code from day one.

Credits used today
- Kiro: (50 credits before use, 0.02 credits used for first prompt)
- Money: NGN 0

Next
- Specs phase (alert parser, screenshot reader, pattern network hook), after approval.

## Day 1, Thu 19 Nov 2026

What I did
- Specced and built the alert parser: spec done (requirements in EARS format, design, 8 tasks) and parse_sms_alert built in src/ghost_credit/parser.py.
- 17 tests passing: 5 example tests, 11 property tests and 1 date fix test.
- Made three fixes after the first build: time-less dates no longer raise DATE_ODD, curly quotes are normalised before pressure phrases are matched, and KNOWN_BANKS is now a real Nigerian bank list.
- Wrote specs for screenshot-reader, pattern-network-hook and verdict-engine. No code for these yet.
- Added the pattern network contract in docs/pattern-network-contract.md.

Kiro features used today
- Specs: requirements, design and task list for four features.
- Property-based tests with Hypothesis, tied to the correctness properties in the design.
- Steering docs: payments-nigeria.md set the red flags and verdict rules the specs follow.

Credits used today
- 

Next
- Run the tasks for screenshot-reader, pattern-network-hook and verdict-engine, after approval.