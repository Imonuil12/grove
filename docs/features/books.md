# Books

**Status:** ⬜ Milestone 3 · **BCT-1:** self-monitoring, goal setting, prompts/cues, feedback on outcomes

## Problem
People start books and stall, and forget most of what they read.

## Mechanics → evidence
| Mechanic | Evidence |
|---|---|
| Add a book via Open Library search (title, author, cover, pages) | product choice |
| Reading goal per book (finish by a date → pages per day) | HAB-2 |
| Log reading sessions (pages or minutes); counts toward a Reading habit automatically | MON-1 |
| Notes and thoughts per chapter | product choice |
| Recall questions generated from the user's own notes, reusing the adaptive quiz engine | LRN-1, LRN-3 |
| Questions come back on a spaced schedule (1, 3, 7, 21 days) | LRN-2 |
| "Finished" card: rating, key takeaway, shareable to the feed | MON-1, SOC-1 |

## User stories
- I search for a book, add it, and set when I want to finish it.
- After reading I log pages and jot thoughts.
- A few days later Grove asks me questions about what I wrote, so I actually remember it.
- When I finish, I get a card to share.

## Data
- `books`: id, user_id, open_library_id, title, author, cover_url, total_pages, status (want/reading/finished),
  target_date, started_at, finished_at, rating, takeaway
- `reading_sessions`: id, book_id, date, pages_from, pages_to, minutes
- `book_notes`: id, book_id, chapter, body (encrypted), created_at
- `recall_items`: id, note_id, question, answer, due_at, interval_days, last_result

## API (sketch)
`GET /books/search?q=` (proxies Open Library) · `GET/POST /books` · `PATCH /books/{id}` · `POST /books/{id}/sessions` ·
`POST /books/{id}/notes` · `GET /recall/due` · `POST /recall/{id}/answer`

## Out of scope (v1)
Importing from Goodreads or Kindle, e-book reading inside Grove.

## Done when
Add, read, note, recall and finish all work end to end; recall scheduling has tests; evidence shown in "Why this works."
