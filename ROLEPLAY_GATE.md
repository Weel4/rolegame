# Deterministic roleplay gate

This is a programmatic gate, not an instruction to Claude to read files.

The only output path that can be guaranteed to withhold unchecked scenes is
`python scripts/roleplay_gate.py run`. It loads all manifest files, verifies
they are present, computes SHA-256 hashes, decodes reversed truth text,
numbers lines, and sends the complete context to the model.

It saves a machine-generated file access log to
`.roleplay-private/read_log.json`. Before printing any scene, it checks the
model's receipts: every mandatory file's SHA-256, existing excerpt and line
numbers, canary, and reported factual claims' source citations.

## Commands

```bash
python -m pip install -r requirements.txt
python scripts/roleplay_gate.py verify-materials
export ANTHROPIC_API_KEY='your-api-key'
export ANTHROPIC_MODEL='your-available-model-id'
python scripts/roleplay_gate.py run --prompt 'Avaan oven.'
```

This requires **separate Anthropic API access** and stores a new local
conversation history. It does not reuse Claude.ai Project conversations.

## Current limitation

At present this repository contains CLAUDE.md but not kaanon.md or totuus.md.
The gate MUST fail until both are supplied, and that fail-closed result is
intentional. Do not upload secret canon or reversed truth to a **public**
GitHub repo. Use a private repo or a private local clone.

GitHub Actions validates repo source integrity, not what a Claude.ai Project
chat read. The runner controls the release of its **own** output, not the
Claude.ai interface. The receipt checks are structural: they establish that
original bytes were supplied and cited, but cannot prove neural attention,
that citations semantically entail story claims, or that unreported claims
were all caught. A canary detects simple coverage failures, not complete
understanding.

The runner prints only `scene`, never the private proof. Audit data lives
under the ignored `.roleplay-private/` directory.
