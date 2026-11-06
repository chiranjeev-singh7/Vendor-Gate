# VendorGate process map

A vendor submission enters as JSON or a selected sample. Intake validates and normalizes the payload, then the ordered pipeline checks completeness, country-specific tax IDs, bank details, name consistency, document validity, and duplicate/risk signals. Each stage records a structured event in an immutable run audit trail.

The deterministic decision engine rejects fraud or blocking findings, marks fixable issues and unresolved name ambiguity pending, and approves submissions with no findings. Communication generates a vendor-facing message and a separate procurement note. The run, decision, events, and messages are saved; approved vendors enter the master list. Run detail supports audit replay and resubmission comparison.
