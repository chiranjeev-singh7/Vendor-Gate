# VendorGate five-minute demo

1. **Happy path (60 sec):** choose `happy_path_clean` and run it. Show the clean approval, risk score, and full stage evidence. Explain that every decision can be traced back to evidence.
2. **Legal name variants (45 sec):** run `edge_name_variants`. Explain that legal suffixes and punctuation are normalized before names are compared.
3. **Holder mismatch (45 sec):** run `edge_holder_mismatch`. Show the specific authorization letter or company bank letter request; the payment risk is routed for review.
4. **Duplicate account (45 sec):** run `edge_duplicate_bank_account`. The vendor receives neutral language while procurement sees the detailed internal finding.
5. **Dashboard (60 sec):** show run history and status counts. Run all samples first if the dashboard is empty.
6. **Resubmission (45 sec):** open the incomplete/expired Pending run, correct the expired tax document and add the bank letter, then compare fields and resolved findings beside the Approved result.
7. **Contact checks (30 sec):** run `edge_email_domain_mismatch`; explain the company email request and the contact-domain mismatch rule IDs.
8. **Close (30 sec):** explain that decisions are rule-based and deterministic, and screening uses fictional lists.

## What I would build next

- OCR and extraction for real PDFs
- Live company registry and sanctions API integrations
- ERP integration
- Multi-person approval workflow
- Vendor self-service portal
