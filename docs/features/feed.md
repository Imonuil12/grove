# Feed

**Status:** ⬜ Milestone 6 · **BCT-1:** social support (unspecified and practical), social reward

## Problem
Progress is easier to keep when someone sees it and cheers you on.

## Mechanics → evidence
| Mechanic | Evidence |
|---|---|
| Follow people; posts visible to followers by default, public profile opt-in | SOC-1, privacy decision |
| Milestone posts generated from real logs: finished book, new PR, habit reaches day 30/66, first 5K | MON-1 |
| Cheers and short comments; no follower counts on the feed itself | MOT-1 (relatedness, not comparison) |
| Users can also post free text and a photo of an achievement | product choice |
| Report and block; posts can be deleted any time | safety |

## Data
`follows`, `posts` (type, ref to source record, body, visibility), `cheers`, `comments`, `reports`

## Out of scope (v1)
Direct messages, groups and challenges (candidate for later, with evidence review).

## Done when
Follow, auto-post a milestone, cheer, comment, report, and delete all work; privacy defaults have tests.
