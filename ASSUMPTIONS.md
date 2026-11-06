# Assumptions

- Rules are deterministic and use RapidFuzz name scores; there is no external registry or OCR integration.
- Supported tax formats include US EIN, India PAN/GSTIN, GB VAT/company number, and German VAT. Other countries route to manual review.
- Every company needs a tax identifier and incorporation/tax evidence; bank-letter and tax-certificate requirements are configurable in `rules.yaml`.
- A bank holder individual's name for a company without authorization evidence is a fixable high-risk issue and remains pending.
- Sanctions and high-risk-country lists are demonstrative fictional data and are not real screening sources.
- Risk and confidence scores are deterministic indicators for triage, not regulatory assessments.
- Run processing is synchronous underneath; SSE streams persisted stage events as each stage executes.
- Resubmission linkage is inferred from matching normalized legal name and country.
- Decisions are deliberately rule-based for determinism and auditability; the UI shows “rule-based” on every decision. LLM polishing is intentionally not included.
- The exact decision-mode label shown on each run is `rule-based`.
- `VENDORGATE_AUTOSEED=true` runs each sample once at startup only when the run history is empty. The seed set includes the six original cases, the corrected resubmission variant, and the email-domain case.
- Contact-domain mismatch and free-mail company contacts are actionable warnings that request confirmation; document issuing-country mismatch is fixable and requires consistent evidence.
- Rule IDs `R-CONTACT-01`, `R-CONTACT-02`, and `R-DOC-02` identify these checks.
