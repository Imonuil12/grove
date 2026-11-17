"""
Adaptive Learning & Personalized Reinforcement Engine (Sprint 10).
Connects user learning progress (intake profile, relational quiz results,
and objective mastery) to chatbot responses to identify struggling concepts,
provide alternative explanations/analogies, and prompt interactive follow-up questions.
"""
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
import re
import models as m
from curriculum import load_catalog

ADAPTIVE_REINFORCEMENT = {
    "amoxicillin": {
        "F1": {
            "title": "Antibiotic Classification & Penicillin Family",
            "analogy": (
                "Think of bacteria and viruses like a mechanical padlock versus a digital computer glitch. "
                "Amoxicillin is a physical metal key engineered specifically for the padlock (bacteria). "
                "Because viruses lack that lock mechanism entirely, amoxicillin has zero effect on viral illnesses like colds or the flu."
            ),
            "follow_up": "To ensure this distinction is clear: if someone catches the winter flu or a runny-nose head cold, why won't amoxicillin help them recover?",
        },
        "F2": {
            "title": "Bacterial Targets vs Viral Colds & Flu",
            "analogy": (
                "Imagine your body's immune defense as security facing two distinct intruders: bacteria are trespassers "
                "building physical walls, while viruses sneak inside your own cells. Amoxicillin attacks those bacterial outer walls, "
                "which is why it works for bacterial strep throat or ear infections, but cannot touch viral colds."
            ),
            "follow_up": "Quick check: if a family member has a viral upper respiratory infection, should they ask a clinician for amoxicillin, or focus on supportive care like rest and fluids?",
        },
        "F3": {
            "title": "Distinguishing Mild Side Effects from Serious Allergic Reactions",
            "analogy": (
                "Think of side effects using a traffic light system: mild stomach upset, nausea, or loose stool is a yellow caution light "
                "(common, manageable, often relieved by taking the dose with food). But facial or lip swelling, widespread hives, wheezing, "
                "or shortness of breath is a flashing red emergency siren—an urgent allergic reaction requiring immediate emergency care."
            ),
            "follow_up": "Before we move forward, quick check: if someone taking amoxicillin develops sudden hives and wheezing, is that an expected mild side effect or a red-flag medical emergency?",
        },
        "D1": {
            "title": "Prescription Adherence & Not Sharing Medications",
            "analogy": (
                "Prescription antibiotics are like customized prescription eyeglasses: what is calibrated precisely for your infection type, "
                "kidney clearance, and body weight could be ineffective or dangerously toxic for someone else."
            ),
            "follow_up": "Why is sharing a prescription antibiotic with a friend dangerous even if their symptoms appear similar to yours?",
        },
        "D2": {
            "title": "Missed Doses & Steady-State Concentration",
            "analogy": (
                "Think of the antibiotic level in your bloodstream like maintaining water temperature in a hot tub. If you miss a dose, "
                "you don't dump in boiling water (doubling up)—that risks overdose side effects. Instead, you resume your normal schedule at the next interval."
            ),
            "follow_up": "If you realize you missed a morning dose and it is already close to your evening dose, what is the clinically recommended step?",
        },
        "D3": {
            "title": "Completing the Full Prescribed Course",
            "analogy": (
                "Stopping an antibiotic early is like putting out 90% of a brushfire and walking away. The weakest bacteria died first, "
                "leaving behind the toughest, most resilient bacteria to rekindle the infection—now resistant to the drug."
            ),
            "follow_up": "Why is it crucial to finish the entire prescribed antibiotic course even if you feel 100% better on day 4?",
        },
        "P1": {
            "title": "Taking With or Without Food & Staying Hydrated",
            "analogy": (
                "Taking your medication with food or a tall glass of water is like cushioning a package with bubble wrap: it buffers your "
                "stomach lining against direct irritation and helps your kidneys flush metabolic byproducts efficiently."
            ),
            "follow_up": "What simple habit can someone follow when swallowing their amoxicillin capsule to minimize nausea or stomach irritation?",
        },
        "P2": {
            "title": "Disclosing Penicillin Allergies to Care Teams",
            "analogy": (
                "Documenting an allergy in your chart acts like a universal safety shield: because amoxicillin is in the penicillin family, "
                "alerting dentists, nurses, and pharmacists prevents accidental cross-prescribing of related beta-lactam antibiotics."
            ),
            "follow_up": "If you have a documented penicillin allergy, why must you make sure all care providers know before starting any antibiotic?",
        },
        "P3": {
            "title": "Recognizing When to Seek Prompt Clinical Help",
            "analogy": (
                "Think of clinical warnings as your body's tripwires: mild queasiness is expected, but persistent severe watery diarrhea "
                "(which could signal C. difficile) or any throat tightness means stop the medication and contact your clinician immediately."
            ),
            "follow_up": "What is one specific red-flag symptom while taking amoxicillin that warrants contacting your doctor right away?",
        },
        "R1": {
            "title": "Mechanism of Action: Bacterial Cell Wall Disruption",
            "analogy": (
                "Imagine bacteria are under heavy internal pressure, like inflated water balloons encased in a mesh cage (peptidoglycan). "
                "Amoxicillin prevents the bacterial bricklayers from sewing the mesh closed. Without that outer wall, the bacteria burst open and die."
            ),
            "follow_up": "In simple terms, why does amoxicillin destroy bacterial cells without damaging our own human cells?",
        },
        "R2": {
            "title": "Cross-Reactivity in the Penicillin Family",
            "analogy": (
                "Amoxicillin and Penicillin are molecular siblings sharing the same chemical backbone (the beta-lactam core ring). "
                "If your immune system has developed antibodies against that shape, it will recognize and attack amoxicillin just like penicillin."
            ),
            "follow_up": "Why does a past anaphylactic reaction to penicillin mean a patient must strictly avoid amoxicillin as well?",
        },
        "R3": {
            "title": "Why Clinical Warnings Surface Based on Intake",
            "analogy": (
                "Clinical warning banners work like a pilot's pre-flight checklist: when your health record flags kidney disease, mono, or "
                "anticoagulant medications, safety rules trigger immediate advisories because algorithmic guidance can never replace your doctor's clinical review."
            ),
            "follow_up": "Why does our system prioritize physician consultation when potential drug interactions or contraindications are flagged?",
        },
    },
    "ibuprofen": {
        "F1": {
            "title": "Nonsteroidal Anti-Inflammatory Drug (NSAID) Classification",
            "analogy": (
                "Ibuprofen is an NSAID—think of it as turning down the volume dial on swelling, pain, and fever at the site of inflammation, "
                "unlike acetaminophen which primarily works in the central nervous system without reducing peripheral tissue swelling."
            ),
            "follow_up": "What medication category does ibuprofen belong to, and how is it fundamentally different from an antibiotic?",
        },
        "D1": {
            "title": "Dosage Limits & Avoiding Excessive Frequency",
            "analogy": (
                "Taking more than the recommended dose of an NSAID does not provide extra pain relief—it hits a ceiling effect where "
                "additional pills only increase strain on your stomach lining and kidneys."
            ),
            "follow_up": "Why is it important to adhere strictly to the recommended dose and time intervals on the ibuprofen label?",
        },
        "P1": {
            "title": "Protecting the Stomach Lining with Food or Milk",
            "analogy": (
                "NSAIDs temporarily decrease prostaglandins that produce your stomach's protective mucus layer. Taking ibuprofen with a snack "
                "or glass of milk creates a physical shield so stomach acid does not cause irritation or ulcers."
            ),
            "follow_up": "Why should ibuprofen always be taken with food, milk, or a full glass of water rather than on an empty stomach?",
        },
        "R1": {
            "title": "Mechanism of Action: COX Enzyme & Prostaglandin Inhibition",
            "analogy": (
                "When tissue is irritated, enzymes called COX act like messengers sounding an alarm bell by creating prostaglandins. "
                "Ibuprofen temporarily blocks the COX enzymes, quieting the pain and swelling alarm at the cellular level."
            ),
            "follow_up": "How does ibuprofen reduce pain and inflammation at the biochemical level?",
        },
    }
}


def get_user_learning_profile(
    username: str,
    drug: str,
    db: Session,
    state: dict = None
) -> Dict[str, Any]:
    """
    Extracts the user's relational learning progress, quiz mistakes,
    and objective mastery status from the database.
    """
    drug_lower = drug.lower()
    catalog = load_catalog(db) if db else {}
    drug_info = catalog.get(drug_lower, {})
    objectives = drug_info.get("objectives", [])
    obj_by_lesson = {obj.lesson_id: obj for obj in objectives}
    obj_by_oid = {obj.oid: obj for obj in objectives}

    struggling_oids = set()
    mastered_oids = set()
    missed_questions = []
    review_items = []

    user = None
    if db and username and not username.startswith("guest_"):
        user = db.query(m.User).filter_by(email=username).one_or_none()

    if user and db:
        # 1. Objective mastery from relational table
        if obj_by_lesson:
            mastery_rows = (
                db.query(m.UserObjectiveMastery)
                .filter_by(user_id=user.id)
                .filter(m.UserObjectiveMastery.lesson_id.in_(list(obj_by_lesson.keys())))
                .all()
            )
            for row in mastery_rows:
                obj = obj_by_lesson.get(row.lesson_id)
                oid = row.objective_code or (obj.oid if obj else None)
                if not oid:
                    continue
                if row.mastery_label == "Known" or (row.crown_level and row.crown_level >= 1):
                    mastered_oids.add(oid)
                elif row.last_practiced is not None and row.mastery_label == "Unknown":
                    struggling_oids.add(oid)

        # 2. Relational quiz failures (is_correct == False)
        failed_responses = (
            db.query(m.UserQuizResponse, m.Question, m.Lesson)
            .join(m.UserQuizAttempt, m.UserQuizResponse.attempt_id == m.UserQuizAttempt.attempt_id)
            .join(m.Question, m.UserQuizResponse.question_id == m.Question.question_id)
            .join(m.Lesson, m.Question.lesson_id == m.Lesson.lesson_id)
            .filter(m.UserQuizAttempt.user_id == user.id)
            .filter(m.UserQuizResponse.is_correct == False)
            .order_by(m.UserQuizResponse.response_id.desc())
            .limit(10)
            .all()
        )
        for resp, question, lesson in failed_responses:
            oid = resp.objective_code or (lesson.objective_code if lesson else None)
            if oid:
                struggling_oids.add(oid)
                missed_questions.append({
                    "oid": oid,
                    "question": resp.question_text or question.question_text,
                    "user_answer": resp.user_answer,
                    "feedback": resp.feedback_text or question.explanation_text,
                    "category": resp.category_label or (lesson.category_label if lesson else None),
                })

        # 3. Queued review items
        if drug_info.get("drug_id"):
            queue_rows = (
                db.query(m.UserLearningQueue)
                .filter_by(user_id=user.id, drug_id=drug_info["drug_id"], kind="review")
                .all()
            )
            for item in queue_rows:
                obj = obj_by_lesson.get(item.lesson_id)
                oid = obj.oid if obj else None
                if oid:
                    struggling_oids.add(oid)
                    review_items.append({
                        "oid": oid,
                        "question": item.question_text or (obj.question if obj else ""),
                        "remediation": item.remediation_text or (obj.remediation_lesson if obj else ""),
                        "category": item.category_label or (obj.category if obj else ""),
                    })

    # 4. Integrate session state (supports guest accounts and in-progress session updates)
    if state:
        for oid, m_dict in (state.get("objective_mastery") or {}).items():
            if isinstance(m_dict, dict):
                lvl = m_dict.get("level")
                streak = m_dict.get("correct_streak", 0)
                crown = m_dict.get("crown_level", 0)
                last_prac = m_dict.get("last_practiced")
                if lvl == "Known" or crown >= 1:
                    mastered_oids.add(oid)
                    struggling_oids.discard(oid)
                elif last_prac is not None and (lvl == "Unknown" or streak == 0):
                    struggling_oids.add(oid)

        for item in state.get("review_items") or []:
            if isinstance(item, dict) and item.get("oid"):
                struggling_oids.add(item["oid"])
                review_items.append(item)

        for oid in (state.get("current_lesson") or {}).get("missed_oids", []):
            struggling_oids.add(oid)

        for res in state.get("last_results") or []:
            if isinstance(res, dict) and not res.get("correct"):
                oid = res.get("oid")
                if oid:
                    struggling_oids.add(oid)
                    missed_questions.append({
                        "oid": oid,
                        "question": res.get("question", ""),
                        "user_answer": "",
                        "feedback": res.get("message", ""),
                        "category": res.get("category", ""),
                    })

    # Mastered objectives take precedence over legacy unmastered markers
    struggling_oids = struggling_oids - mastered_oids

    # Format human-readable struggling summary
    struggling_details = []
    drug_reinforce = ADAPTIVE_REINFORCEMENT.get(drug_lower, {})
    for oid in sorted(struggling_oids):
        obj = obj_by_oid.get(oid)
        title = drug_reinforce.get(oid, {}).get("title") or (obj.objective_text if obj else f"Objective {oid}")
        category = obj.category if obj else "Medication Concept"
        struggling_details.append(f"{oid} ({category}): {title}")

    state = state or {}
    intake = state.get("intake") or {}
    
    # Read preferences from UserLearningState if available
    db_exp = None
    db_arch = None
    if user and db:
        user_state_row = db.query(m.UserLearningState).filter_by(user_id=user.id).one_or_none()
        if user_state_row:
            db_exp = user_state_row.experience_level
            db_arch = user_state_row.archetype

    experience_level = (state.get("experience_level") or intake.get("experience_level") or db_exp or "beginner").lower()
    archetype = state.get("archetype") or intake.get("archetype") or db_arch or "needs more explanations"

    return {
        "username": username,
        "drug": drug_lower,
        "experience_level": experience_level,
        "archetype": archetype,
        "struggling_oids": sorted(list(struggling_oids)),
        "mastered_oids": sorted(list(mastered_oids)),
        "missed_questions": missed_questions,
        "review_items": review_items,
        "struggling_summary": "; ".join(struggling_details) if struggling_details else "None flagged (learner is on track)",
    }


def format_learning_profile_summary(profile: Dict[str, Any]) -> str:
    """Formats diagnostic progress for the LLM system prompt."""
    struggling = profile.get("struggling_summary", "None")
    missed = profile.get("missed_questions", [])
    missed_text = ""
    if missed:
        unique_missed = []
        seen = set()
        for m_item in missed:
            q = m_item.get("question")
            if q and q not in seen:
                seen.add(q)
                unique_missed.append(f"- Concept {m_item.get('oid')}: '{q}'")
        missed_text = "\nRecent Missed Quiz Questions:\n" + "\n".join(unique_missed[:4])

    mastered = ", ".join(profile.get("mastered_oids", [])) or "None yet"

    return (
        f"LEARNER KNOWLEDGE DIAGNOSTIC & MASTERY STATUS:\n"
        f"- Concepts Needing Reinforcement / Struggling Topics: {struggling}\n"
        f"- Mastered Objectives: {mastered}\n"
        f"{missed_text}\n"
    )


def is_review_intent(message: str) -> bool:
    """Detects whether the user is explicitly asking to review their mistakes or struggling topics."""
    msg = message.lower().strip()
    patterns = [
        r"what do i need to review",
        r"what (am i|did i) struggl",
        r"concepts i struggle with",
        r"what should i review",
        r"review (my )?(mistakes|missed|struggl|errors|quiz)",
        r"test me on what i (missed|got wrong)",
        r"what did i get wrong",
        r"help me (study|practice)",
        r"my weak (spots|areas)",
        r"practice (my )?(missed|mistakes)",
        r"can we review",
        r"give me a review",
    ]
    return any(re.search(pat, msg) for pat in patterns)


def generate_proactive_review_response(
    profile: Dict[str, Any],
    drug: str,
    archetype: str,
    db: Session = None
) -> str:
    """Generates a proactive review session addressing the learner's specific missed questions."""
    drug_lower = drug.lower()
    catalog = load_catalog(db) if db else {}
    drug_info = catalog.get(drug_lower, {})
    display_name = drug_info.get("display_name", drug.capitalize())
    drug_reinforce = ADAPTIVE_REINFORCEMENT.get(drug_lower, {})

    struggling = profile.get("struggling_oids", [])
    missed = profile.get("missed_questions", [])

    if not struggling and not missed:
        return (
            f"🌟 **Great news!** Your recent quiz and checkpoint attempts for {display_name} show strong understanding "
            f"across all completed units with zero flagged struggling concepts right now.\n\n"
            f"We can explore deeper topics like clinical interactions, or if you'd like, you can ask me any question about "
            f"dosage, side effects, or pharmacology to keep your knowledge sharp!"
        )

    # Pick the top struggling concept
    target_oid = struggling[0] if struggling else (missed[0].get("oid") if missed else "F1")
    reinforcement = drug_reinforce.get(target_oid, {})
    title = reinforcement.get("title") or f"Objective {target_oid}"
    analogy = reinforcement.get("analogy", "")
    follow_up = reinforcement.get("follow_up", "How would you explain this concept in your own words?")

    # Find the specific missed question if available
    missed_q = next((m_item.get("question") for m_item in missed if m_item.get("oid") == target_oid), None)
    missed_note = f"\n*On a recent quiz, this question gave you some trouble: \"{missed_q}\"*" if missed_q else ""

    arch = archetype.lower()
    if arch == "the skeptic":
        opening = f"Let's look at the evidence on a concept where your recent answers showed some room for reinforcement: **{title}**."
    elif arch == "trying not to get worse":
        opening = f"Here is a key safety concept from your recent questions that makes a real difference in preventing mistakes: **{title}**."
    elif arch == "all in until i'm not":
        opening = f"Quick review on your recent missed concept: **{title}**."
    else:  # needs more explanations
        opening = f"I took a look at your recent progress for {display_name}, and I noticed **{title}** could use a little extra reinforcement."

    return (
        f"{opening}{missed_note}\n\n"
        f"💡 **Alternative Perspective:**\n{analogy}\n\n"
        f"🎯 **Interactive Check-In:**\n{follow_up}"
    )


def build_adaptive_explanation(
    obj: Any,
    base_text: str,
    archetype: str,
    profile: Dict[str, Any],
    drug: str
) -> str:
    """
    Applies an adaptive explanation with an alternative analogy and follow-up question
    when the learner is struggling with the requested objective.
    """
    drug_lower = drug.lower()
    drug_reinforce = ADAPTIVE_REINFORCEMENT.get(drug_lower, {})
    reinforcement = drug_reinforce.get(obj.oid)

    is_struggling = obj.oid in profile.get("struggling_oids", [])

    if not is_struggling or not reinforcement:
        return base_text

    analogy = reinforcement.get("analogy", "")
    follow_up = reinforcement.get("follow_up", "")
    title = reinforcement.get("title", obj.objective_text)

    arch = archetype.lower()
    if arch == "the skeptic":
        header = f"🔍 *Reinforcement Note:* I noticed this concept (**{title}**) came up on a recent quiz. Let's look at the underlying mechanics so the reasoning is unmistakable:"
        bridge = "Here is an intuitive model to ground the evidence:"
    elif arch == "trying not to get worse":
        header = f"🛡️ *Safety Focus:* This topic (**{title}**) was flagged in your recent learning queue. Getting this right is vital for protecting your health:"
        bridge = "Here is the key distinction to keep you safe:"
    elif arch == "all in until i'm not":
        header = f"📌 *Key Concept:* (Reviewing **{title}** from your recent quiz)"
        bridge = "Core takeaway:"
    else:  # needs more explanations
        header = f"💡 *Personalized Reinforcement:* I noticed this topic (**{title}**) was tricky on a recent quiz. Let's explore it with a fresh picture:"
        bridge = "Think of it this way:"

    adaptive_body = f"{header}\n\n{bridge}\n{analogy}\n\n{base_text}\n\n❓ **Quick Check-In Before We Move On:**\n{follow_up}"
    return adaptive_body
