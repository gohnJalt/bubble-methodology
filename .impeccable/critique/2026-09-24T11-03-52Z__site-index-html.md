---
target: site/index.html
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:/Users/kaanakkas/Desktop/projects/bubble-methodology/site/index.html"
target_fingerprint: "sha256:6c60fc851f766e757f26a9dfe90dee6c512bfa70534936919ffeaa33d14d4be4"
target_path: /Users/kaanakkas/Desktop/projects/bubble-methodology/site/index.html
timestamp: 2026-09-24T11-03-52Z
slug: site-index-html
---
Method: dual-agent (A: design review · B: detector + contrast). Browser overlay skipped: Chrome extension not connected; headless Chrome used for screenshots and console.

## Design Health Score
| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Provisional/stale flagged well; "Readings rebuilt" hidden on mobile |
| 2 | Match System / Real World | 3 | Macro "neutral/loose" sits beside state "normal": near-synonyms, two signals |
| 3 | User Control and Freedom | 3 | Hash routes give back/links; no chart zoom reset (modebar off) |
| 4 | Consistency and Standards | 2 | Cross-market chart paints BIST in bubble-red, FTSE in z-green; stale banner shows internal keys |
| 5 | Error Prevention | 2 | Impossible windows offered (30y on BIST); ongoing-episode drawdowns shown as final |
| 6 | Recognition Rather Than Recall | 3 | Heat strip has no legend/current-row marker; macro values lack units |
| 7 | Flexibility and Efficiency | 2 | No export, no chart tools, heat strip not clickable |
| 8 | Aesthetic and Minimalist Design | 3 | Calm; "to Sep 2026 · provisional" repeated 4x |
| 9 | Error Recovery | 2 | Too-short-history state is a dead end with a false subtitle |
| 10 | Help and Documentation | 3 | Methodology strong but not linked from what it explains |
| **Total** | | **26/40** | **Acceptable** |

## Priority Issues
- [P1] Keyboard focus lost on every window change (sidebar innerHTML rebuilt in render) -> harden
- [P1] Ongoing-episode drawdowns shown as final (FTSE 2025-10: -0.8% over an unfinished 24m window) -> harden (build.py + page)
- [P1] Too-short-history error is a dead end; subtitle claims a 30y trend that doesn't exist; impossible chips stay enabled -> clarify
- [P2] Cross-market chart reuses semantic colours (bubble red, z green) as market identities -> colorize
- [P2] Mobile: window picker precedes the reading, nav scroll hidden, legend collides with range buttons, freshness hidden -> adapt

## Detector
1 finding: overused-font (Inter). Real match, taste call; not a defect. All text contrast >= 4.5:1 (lowest: n/a pill 4.90). Trend line 3.13:1 is the tightest mark. No console errors on #/, #/new_york, #/method.
