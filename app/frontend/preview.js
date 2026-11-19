// Pages for trackers that are designed but not built yet (Habits, Books, Training, Feed).
// They show what's coming, the research behind it, and let the coach help today.
import { esc, icon, renderWhy } from "./core.js";
import { mountShell } from "./shell.js";

const PAGES = {
  habits: {
    tone: "leaf", milestone: "Milestone 2",
    title: "Habits that stick",
    lead: "Turn a vague goal into a small, specific plan, check in each day, and watch it become automatic.",
    coming: [
      "Write each habit as a plan: “After I pour my coffee, I'll read 10 pages at the kitchen table.”",
      "Start tiny, then grow it once it feels easy.",
      "One-tap daily check-ins, ordered by the time you planned.",
      "A 66-day growth arc for each habit, drawn as a branch of your tree.",
      "“Never miss twice”: one missed day is normal, and two in a row gets a gentle restart plan.",
      "Reminders at the time you chose.",
    ],
    evidence: ["HAB-2", "HAB-3", "HAB-1", "MON-1", "REM-1"],
    prompt: "Help me turn a goal into a small habit with an if-then plan.",
    ask: "Plan my first habit with the coach",
  },
  books: {
    tone: "sky", milestone: "Milestone 3",
    title: "Read more, remember more",
    lead: "Add a book, log your reading, jot your thoughts, and let Grove quiz you on your own notes so it sticks.",
    coming: [
      "Search any book (Open Library) and set when you want to finish it.",
      "Log reading sessions in pages or minutes; it counts toward your Reading habit.",
      "Notes and thoughts for each chapter.",
      "Recall questions made from your notes, coming back after 1, 3, 7 and 21 days.",
      "A “Finished” card with your rating and key takeaway, ready to share.",
    ],
    evidence: ["LRN-1", "LRN-2", "LRN-3", "MON-1"],
    prompt: "Help me build a daily reading habit and remember what I read.",
    ask: "Plan my reading with the coach",
  },
  training: {
    tone: "sun", milestone: "Milestone 4",
    title: "Train with a plan",
    lead: "Log lifts and runs, hit the weekly activity guideline, and see real progress instead of daily noise.",
    coming: [
      "A weekly ring: 150 active minutes and 2 strength days.",
      "Strength log with sets, reps, weight and personal records.",
      "“Add weight” suggestions when you beat your target reps.",
      "Runs and cardio with pace, plus a beginner run/walk plan.",
      "Weight as a 7-day average trend, with optional calories and protein.",
    ],
    evidence: ["FIT-1", "FIT-2", "FIT-3", "WT-1", "COG-1"],
    prompt: "Help me plan a simple week of workouts that meets the activity guidelines.",
    ask: "Plan my week with the coach",
  },
  feed: {
    tone: "plum", milestone: "Milestone 6",
    title: "Share the wins",
    lead: "Celebrate milestones with the people who keep you going: finished books, new records, 30-day habits.",
    coming: [
      "Follow friends; posts are visible to followers by default.",
      "Milestones posted from your real logs: a finished book, a new record, your first 5K.",
      "Cheers and short comments, with no follower counts on the feed itself.",
      "Report, block, and delete any post at any time.",
    ],
    evidence: ["SOC-1", "MON-1", "MOT-1"],
    prompt: "How can I use friends or accountability to stick with my goals?",
    ask: "Ask the coach about accountability",
  },
};

export function mountPreview(key) {
  if (!mountShell()) return;
  const p = PAGES[key];
  const page = document.getElementById("page");
  page.innerHTML = `
    <div class="page-head">
      <span class="status">Coming in ${esc(p.milestone)}</span>
      <h1 style="margin-top:10px">${esc(p.title)}</h1>
      <p>${esc(p.lead)}</p>
    </div>
    <div class="grid grid-2">
      <section class="card">
        <h2><span class="card-icon tone-${p.tone}">${icon(key)}</span> What you'll be able to do</h2>
        <ul class="list-check">${p.coming.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
      </section>
      <section class="card">
        <h2><span class="card-icon tone-leaf">${icon("coach")}</span> Start today with your coach</h2>
        <p class="muted">The tracker is on its way. Your coach already knows the research and can help you make a plan now.</p>
        <a class="btn btn-primary" href="coach.html?ask=${encodeURIComponent(p.prompt)}">${esc(p.ask)} ${icon("arrow", 16)}</a>
      </section>
    </div>
    <div id="why"></div>`;
  renderWhy(page.querySelector("#why"), p.evidence, "Each part of this tracker is designed around these findings:");
}
