# Evidence library

Every study Grove relies on lives here, once, with an ID. Feature specs, code comments and marketing copy
cite the ID (for example `HAB-1`) instead of repeating the study. Rules for adding and using evidence are in
the `research-backed` skill (`.claude/skills/research-backed/SKILL.md`).

## Grades

| Grade | Meaning | May be used in marketing? |
|---|---|---|
| **A** | Meta-analysis, systematic review, or official guideline / consensus statement | Yes |
| **B** | Randomized controlled trial or a well-designed single study | Yes, worded as "a study found" |
| **C** | Practitioner framework, expert opinion, or widely used program without strong trial evidence | No. Internal design input only |

Every entry must be a real, checkable source. If a detail (a number, a sample size) can't be verified, leave it out.

---

## Habits and behavior change

### HAB-1 · Habits take time to become automatic, and one missed day doesn't break them · **B**
Lally, P., van Jaarsveld, C. H. M., Potts, H. W. W., & Wardle, J. (2010). How are habits formed: Modelling habit
formation in the real world. *European Journal of Social Psychology, 40*(6), 998–1009.
- **Finding:** Automaticity rose along a curve and leveled off after a median of 66 days (range 18–254).
  Missing one opportunity did not materially affect habit formation.
- **We use it for:** the 66-day growth arc; "never miss twice" instead of a streak that resets to zero.

### HAB-2 · "If-then" plans improve follow-through · **A**
Gollwitzer, P. M., & Sheeran, P. (2006). Implementation intentions and goal achievement: A meta-analysis of
effects and processes. *Advances in Experimental Social Psychology, 38*, 69–119.
- **Finding:** Across 94 independent tests, forming implementation intentions ("when situation X, I will do Y")
  had a medium-to-large effect on goal attainment (d = .65).
- **We use it for:** every habit is written as "After I [cue], I will [action] at [place/time]."

### HAB-3 · Habits are triggered by stable context cues · **A**
Wood, W., & Neal, D. T. (2007). A new look at habits and the habit–goal interface. *Psychological Review, 114*(4), 843–863.
- **Finding:** Habits are cued by context (time, place, preceding action), not by goals or intentions alone.
- **We use it for:** asking for a cue and a place, and reminding at that time.

### HAB-4 · Start tiny and anchor to an existing routine · **C**
Fogg, B. J. (2019). *Tiny Habits: The Small Changes That Change Everything.* Houghton Mifflin Harcourt.
- **Use:** design input for "start tiny, grow later" and anchoring. Not a marketing claim on its own;
  the anchoring part is supported by HAB-2 and HAB-3.

### MON-1 · Tracking progress helps people reach goals, more so when recorded and shared · **A**
Harkin, B., Webb, T. L., Chang, B. P. I., Prestwich, A., Conner, M., Kellar, I., Benn, Y., & Sheeran, P. (2016).
Does monitoring goal progress promote goal attainment? A meta-analysis of the experimental evidence.
*Psychological Bulletin, 142*(2), 198–229.
- **Finding:** Prompting people to monitor progress improved goal attainment. Effects were larger when progress
  was physically recorded and when it was reported to others or made public.
- **We use it for:** logging in every tracker; the feed and weekly review.

### REM-1 · Reminders and prompts help health behaviors · **A**
Fry, J. P., & Neff, R. A. (2009). Periodic prompts and reminders in health promotion and health behavior
interventions: Systematic review. *Journal of Medical Internet Research, 11*(2), e16.
- **Finding:** Most included studies found that periodic prompts had a positive effect on behavior.
- **We use it for:** reminders at the time the user chose in their plan.

### BCT-1 · A shared language for behavior change techniques · **A**
Michie, S., Richardson, M., Johnston, M., Abraham, C., Francis, J., Hardeman, W., Eccles, M. P., Cane, J., &
Wood, C. E. (2013). The behavior change technique taxonomy (v1) of 93 hierarchically clustered techniques.
*Annals of Behavioral Medicine, 46*(1), 81–95.
- **We use it for:** tagging each Grove mechanic with the technique it implements (goal setting, action planning,
  self-monitoring, prompts/cues, social support, feedback on behavior).

### MOT-1 · Autonomy, competence and relatedness drive lasting motivation · **A**
Ryan, R. M., & Deci, E. L. (2000). Self-determination theory and the facilitation of intrinsic motivation,
social development, and well-being. *American Psychologist, 55*(1), 68–78.
- **We use it for:** coach tone (supportive, never shaming), letting users choose their goals and display mode,
  showing competence through progress, the feed for relatedness.

### GAM-1 · Gamification works for some people in some contexts · **A**
Hamari, J., Koivisto, J., & Sarsa, H. (2014). Does gamification work? A literature review of empirical studies on
gamification. *Proceedings of the 47th Hawaii International Conference on System Sciences*, 3025–3034.
- **Finding:** Mostly positive effects, but dependent on context and the user.
- **We use it for:** Game mode is optional, not the default for everyone.

## Learning and reading

### LRN-1 · Testing yourself beats rereading · **B**
Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term
retention. *Psychological Science, 17*(3), 249–255.
- **Finding:** Retrieval practice produced better retention on delayed tests than restudying.
- **We use it for:** recall questions generated from the user's own book notes.

### LRN-2 · Spacing out review improves long-term memory · **A**
Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall
tasks: A review and quantitative synthesis. *Psychological Bulletin, 132*(3), 354–380.
- **We use it for:** scheduling recall questions over days and weeks after a reading session.

### LRN-3 · Practice testing and spaced practice are the most useful study techniques · **A**
Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J., & Willingham, D. T. (2013). Improving students' learning
with effective learning techniques. *Psychological Science in the Public Interest, 14*(1), 4–58.
- **Finding:** Of ten common techniques, practice testing and distributed practice were rated high utility;
  highlighting and rereading were rated low.
- **We use it for:** why Books asks questions instead of just storing highlights.

## Physical activity and body

### FIT-1 · How much activity adults need · **A**
Bull, F. C., et al. (2020). World Health Organization 2020 guidelines on physical activity and sedentary behaviour.
*British Journal of Sports Medicine, 54*(24), 1451–1462.
- **Guideline:** Adults: 150–300 minutes of moderate (or 75–150 vigorous) aerobic activity per week, plus
  muscle-strengthening activity on 2 or more days.
- **We use it for:** the weekly activity ring and strength-day target.

### FIT-2 · Progressive overload for strength · **A**
American College of Sports Medicine. (2009). Progression models in resistance training for healthy adults.
*Medicine & Science in Sports & Exercise, 41*(3), 687–708.
- **Guideline:** Gradually increase training stimulus; for novices, moderate loads for about 8–12 repetitions,
  and increase load when the target repetitions can be exceeded.
- **We use it for:** "time to add weight" suggestions in Training.

### FIT-3 · Protein intake for people who strength train · **A**
Morton, R. W., et al. (2018). A systematic review, meta-analysis and meta-regression of the effect of protein
supplementation on resistance training-induced gains in muscle mass and strength in healthy adults.
*British Journal of Sports Medicine, 52*(6), 376–384.
- **Finding:** Benefits to muscle mass leveled off at about 1.6 g of protein per kg of body weight per day.
- **We use it for:** the optional protein target. Not medical advice.

### WT-1 · Daily weighing, viewed as a trend, supports weight management · **B**
Steinberg, D. M., Bennett, G. G., Askew, S., & Tate, D. F. (2015). Weighing every day matters: Daily weighing
improves weight loss and adoption of weight control behaviors. *Journal of the Academy of Nutrition and
Dietetics, 115*(4), 511–518.
- **We use it for:** weight logging with a 7-day average trend line.

### COG-1 · Aerobic exercise and the brain · **B**
Erickson, K. I., et al. (2011). Exercise training increases size of hippocampus and improves memory.
*Proceedings of the National Academy of Sciences, 108*(7), 3017–3022.
- **Finding:** In older adults, a year of aerobic exercise increased hippocampal volume and improved memory
  compared with stretching.
- **We use it for:** explaining how physical and cognitive growth connect. Word carefully: older adults, one trial.

### RUN-1 · Couch to 5K · **C**
NHS. *Couch to 5K* running plan (9 weeks, three runs per week, run/walk intervals).
- **Use:** structure for the beginner running plan. Widely used public program, not a trial.

### SLP-1 · Adults need 7 or more hours of sleep · **A**
Watson, N. F., et al. (2015). Recommended amount of sleep for a healthy adult: A joint consensus statement of the
American Academy of Sleep Medicine and Sleep Research Society. *Sleep, 38*(6), 843–844.
- **We use it for:** the sleep habit template's default target.

### MND-1 · Meditation programs and well-being · **A**
Goyal, M., et al. (2014). Meditation programs for psychological stress and well-being: A systematic review and
meta-analysis. *JAMA Internal Medicine, 174*(3), 357–368.
- **Finding:** Moderate evidence that mindfulness meditation programs improve anxiety, depression and pain.
- **We use it for:** the meditation habit template. Do not claim it treats any condition.

## Social support

### SOC-1 · Doing it with others helps people stick with it · **B**
Wing, R. R., & Jeffery, R. W. (1999). Benefits of recruiting participants with friends and increasing social
support for weight loss and maintenance. *Journal of Consulting and Clinical Psychology, 67*(1), 132–138.
- **Finding:** People who joined with friends and received social support were more likely to complete the
  program and keep the weight off.
- **We use it for:** followers, the feed, cheering on milestones.
