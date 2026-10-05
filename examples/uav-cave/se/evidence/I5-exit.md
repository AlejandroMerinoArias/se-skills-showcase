# I5 exit — mission completion and safety verified

- **Code:** branch `i4-mission`. Plans: `docs/superpowers/plans/2026-10-03-opening-tier.md` (opening tier, D-51)
  and the I5 fixes recorded in the commit history from `f188464` to `ed342de`.
- **Unit tests:** `wsl.exe bash tools/run_tests.sh` gives 266 test cases, 0 failures (commit ed342de plus annotation
  fixes). Merged with the sim results of acceptance series 3 run 2 into `build_results/i5_junit.xml` (279 test cases,
  0 failures); every test-linked I5 requirement shows PASS in `se/generated/matrix.md`.
- **Simulation:** acceptance series 3 (`evidence/I5-acceptance-3.md`), three consecutive runs on commit 77b2ed5:
  four lanterns and back at the entrance in 1529, 1556 and 1695 s; coverage 94.1, 92.5 and 91.3 %; runs 2 and 3
  passed every sim test; run 1 failed the 0.5 m proximity criterion on non-surface points by the mouth. No contact
  in any run. SYS-P-005 (2 of 3) met.
- **Requirements verified:** SYS-P-002 (sim test), SYS-P-004 (analysis, coverage in all three runs), SYS-P-005
  (demonstration, the series), SYS-S-001 (demonstration, no contact in three runs; I3 inspection), ITEM-D-046 to
  ITEM-D-050 and ITEM-D-052 (unit tests). ITEM-D-051 retired (Q-42).
- **CRIT-A:** reviewed by the developer only - no independent whole-branch review ran in I5 (I3 had one on Opus).
  The customer approved marking the CRIT-A requirements implemented with that caveat stated (Q-43).
- **Changes during I5:** D-38 to D-52 (`architecture.md`); customer decisions Q-29 to Q-43; D-45 retired; D-41's
  turn rate reverted (D-52).

Carried risks:
- **Close-pass criterion vs. scene objects:** a non-colliding object near the mouth can put mapped points on the route
  (run 20261004-022644). It failed the 0.5 m criterion once in three runs without any contact.
- **Timing margin:** returns at 1529-1695 s leave 105-271 s against 1800 s; about 20 % of mission time is still
  spent stopped at path changes and blocked-path replans (`early_request_m` option untested, E-49 not run).
- **Coverage margin:** 91-94 % against 90 %; the first-gallery floor between rubble is never seen by the forward
  camera, and its share of the coverage band decides the result.
