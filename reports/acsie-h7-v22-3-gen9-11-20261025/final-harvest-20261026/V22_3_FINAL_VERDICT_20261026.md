# ACSIE H7 V22.3 final qualification evidence — 2026-10-26

# ACSIE H7 V22.3 Final Harvest and 60-Slot Audit — 2026-10-26

## Verdict

NOT_QUALIFIED — DO NOT PROMOTE. The single Kaggle status snapshot returned KernelWorkerStatus.ERROR. All five seed-log tail probes ended with OPEN_ENDED_SELF_EXTENDING_GATE=FAIL. The output listing exposed only 56/60 generation pair-audit JSON files; seed 2026100303 generations 08–11 are absent. Neither run_manifest.json nor foundry-summary.json was present in the single-page output listing, so the executed runner/archive hash match and the run-manifest target_access_during_discovery flag are UNVERIFIED.

## Recovery and provenance

- Exactly one worker status snapshot; no polling loop, rerun, or restart.
- Output list: 89 entries, no next page. The whitelist selected 56 generation JSONs and five seed logs; the large audit-events JSONL was deliberately excluded.
- run_manifest.json: NOT FOUND in the output listing. foundry-summary.json: NOT FOUND in the output listing.
- Local runner SHA-256: 82eba365a03c717126a31d2fd0dd2a88a3d9da14107e76bdae101ca43655885e.
- Local embedded archive SHA-256: eeef65e6bb74dbf25b6b101874acc283604b0c3bb6bfb655c9538ac837b614d8.
- Executed runner/archive digest comparison: UNVERIFIED. The manifest required to bind output to executed source is absent.
- run-manifest target_access_during_discovery=false: UNVERIFIED. Seed 0302's recovered summary does say target_identity_available_to_runtime=false and holdout/transfer/OOD selection flags are false; these are related but not substitutes for the absent manifest field.


FINAL VERDICT: NOT_QUALIFIED — DO NOT PROMOTE. Gate 1 is NOT cleared.
