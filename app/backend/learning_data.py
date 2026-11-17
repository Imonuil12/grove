from dataclasses import dataclass
from typing import List

@dataclass
class Objective:
    oid: str
    category: str
    objective_text: str
    lesson_text: str
    question: str
    accepted_keyword_sets: List[List[str]]
    remediation_lesson: str
    hint: str | None = None


# CDC sources: https://www.cdc.gov/high-blood-pressure/about/
# https://www.cdc.gov/high-blood-pressure/risk-factors/
# https://www.cdc.gov/high-blood-pressure/prevention/
# https://www.cdc.gov/high-blood-pressure/measure/
# https://www.cdc.gov/stroke/about/
TOPIC_LESSONS = {
    "condition:hypertension": [
        Objective(
            "BP1", "Condition basics", "Recognize the term hypertension",
            "Hypertension means blood pressure stays higher than it should over time. Blood pressure changes throughout the day, so a care team uses readings to assess it.",
            "What is the medical name for blood pressure that stays too high?",
            [["hypertension"]],
            "The medical term is hypertension. It refers to blood pressure that stays too high.",
            "Think of a term that starts with 'hyper', meaning above normal.",
        ),
        Objective(
            "BP2", "Condition basics", "Identify where blood pressure acts",
            "Blood pressure describes how strongly blood pushes against the artery walls as the heart pumps.",
            "What blood vessels have walls that blood pushes against when we measure blood pressure?",
            [["arteries"], ["artery"]],
            "Blood pushes against the walls of the arteries. Measuring that pressure gives a blood pressure reading.",
            "Think of the vessels that carry blood away from the heart.",
        ),
        Objective(
            "BP3", "Why it matters", "Connect high blood pressure to stroke risk",
            "Over time, high blood pressure can damage blood vessels and raise the chance of a stroke.",
            "What brain emergency can high blood pressure make more likely?",
            [["stroke"]],
            "High blood pressure increases the risk of stroke.",
            "Think of an emergency caused when blood flow to part of the brain is interrupted or a blood vessel in the brain bursts.",
        ),
        Objective(
            "BP4", "Why it matters", "Recognize the effect on the kidneys",
            "High blood pressure can damage the small blood vessels in the kidneys. Over time, this can affect how well they filter the blood.",
            "Which organs that filter the blood can be damaged by high blood pressure?",
            [["kidneys"], ["kidney"]],
            "The kidneys filter the blood. High blood pressure can harm them over time.",
            "Think of the organs that remove waste from the blood and make urine.",
        ),
        Objective(
            "BP5", "Risk factors", "Identify a dietary risk factor",
            "Regularly eating foods high in sodium can contribute to high blood pressure. Sodium is a component of table salt and is common in many packaged foods.",
            "What mineral in table salt can raise blood pressure when you eat too much of it?",
            [["sodium"]],
            "Sodium is the mineral in table salt that can contribute to high blood pressure when consumed in excess.",
            "Table salt is made from chloride and one other mineral. Look for that mineral on nutrition labels.",
        ),
        Objective(
            "BP6", "Risk factors", "Recognize a risk factor outside your control",
            "High blood pressure can run in families. Knowing your family history helps you discuss risk with your care team.",
            "What information about your relatives' health can help explain your risk of high blood pressure?",
            [["family history"], ["family", "high blood pressure"], ["family", "hypertension"], ["runs in the family"]],
            "Family history can help explain risk. A care team can use that information when discussing preventive care.",
            "Think about whether close relatives, such as a parent or sibling, have had high blood pressure.",
        ),
        Objective(
            "BP7", "Prevention and early signs", "Explain why blood pressure checks matter",
            "Many people with high blood pressure feel well. A blood pressure check can help detect it early, even when there are no noticeable symptoms.",
            "What should you get measured to check for hypertension even when you feel well?",
            [["blood pressure"], ["bp"]],
            "Get your blood pressure measured. How you feel cannot tell you whether your blood pressure is high.",
            "Think of the reading that is usually taken with a cuff around the upper arm.",
        ),
        Objective(
            "BP8", "Prevention and early signs", "Identify a practical lower-sodium swap",
            "When comparing versions of the same packaged food, checking the sodium line on the label can help you choose the one with less sodium.",
            "When choosing between two versions of the same canned food, look for more sodium or less sodium?",
            [["less sodium"], ["lower sodium"], ["low sodium"], ["less salt"], ["no added salt"]],
            "Look for the option with less sodium. Compare the sodium amounts for the same serving size.",
            "Compare the sodium line on the two labels and look for the smaller amount per serving.",
        ),
    ],
}


AMOXICILLIN_OBJECTIVES: List[Objective] = [
    Objective(
        oid="F1",
        category="Facts",
        objective_text="Identify amoxicillin as an antibiotic (penicillin family).",
        lesson_text=(
            "Amoxicillin is an antibiotic in the penicillin (beta-lactam) family.\n\n"
            "Antibiotics target bacteria. They do not treat viral infections like colds or flu.\n\n"
            "People with a penicillin allergy may need a different medication."
        ),
        question="What kind of medication is amoxicillin?",
        accepted_keyword_sets=[["antibiotic"], ["penicillin"], ["beta", "lactam"]],
        remediation_lesson="Amoxicillin is an antibiotic (penicillin/beta-lactam). It targets bacteria, not viruses.",
    ),
    Objective(
        oid="F2",
        category="Facts",
        objective_text="Recognize it treats certain bacterial infections (not viral colds/flu).",
        lesson_text=(
            "Amoxicillin may be prescribed for certain bacterial infections.\n\n"
            "It does not work against viruses (like the common cold or flu).\n\n"
            "A clinician decides whether an infection is likely bacterial and if this antibiotic is appropriate."
        ),
        question="Does amoxicillin treat viral infections like the common cold?",
        accepted_keyword_sets=[["no"], ["does", "not"], ["not", "viral"]],
        remediation_lesson="Antibiotics like amoxicillin treat bacteria; colds/flu are viral so they usually don’t help.",
    ),
    Objective(
        oid="F3",
        category="Facts",
        objective_text="Distinguish common side effects vs serious allergy warning signs.",
        lesson_text=(
            "Common side effects can include stomach upset, nausea, or mild diarrhea.\n\n"
            "Serious allergy warning signs can include hives, swelling of the face/lips, wheezing, trouble breathing, "
            "or a severe rash.\n\n"
            "Trouble breathing or swelling can be urgent—seek medical care."
        ),
        question="Name ONE serious allergic reaction sign someone should take seriously.",
        accepted_keyword_sets=[["trouble", "breathing"], ["swelling"], ["hives"], ["wheezing"], ["face", "swelling"]],
        remediation_lesson="Serious allergy signs: trouble breathing, hives, wheezing, swelling (face/lips).",
    ),
    Objective(
        oid="D1",
        category="Dosage",
        objective_text="Understand 'take exactly as prescribed' and do not share antibiotics.",
        lesson_text=(
            "Follow the prescription label exactly.\n\n"
            "Do not share antibiotics and do not use leftovers without clinician guidance.\n\n"
            "Different infections and people require different prescriptions."
        ),
        question="Is it okay to share your amoxicillin with someone else who feels sick?",
        accepted_keyword_sets=[["no"], ["not", "share"], ["never", "share"]],
        remediation_lesson="Don’t share antibiotics—prescriptions are specific to a person + infection.",
    ),
    Objective(
        oid="D2",
        category="Dosage",
        objective_text="Know a general missed-dose rule of thumb (non-specific).",
        lesson_text=(
            "General rule (still follow your label):\n\n"
            "If you miss a dose, take it when you remember unless it’s close to the next scheduled dose.\n\n"
            "Do not double up unless a clinician specifically tells you to."
        ),
        question="If you miss a dose, should you double the next one to 'catch up'?",
        accepted_keyword_sets=[["no"], ["do", "not", "double"], ["not", "double"]],
        remediation_lesson="Missed dose basics: don’t double up. Follow the label; ask a pharmacist if unsure.",
    ),
    Objective(
        oid="D3",
        category="Dosage",
        objective_text="Understand why finishing the course of antibiotics matters (general).",
        lesson_text=(
            "Stopping early can allow bacteria to come back.\n\n"
            "Finishing the course (as directed) helps reduce relapse and may reduce resistance risk.\n\n"
            "If side effects happen, consult a clinician rather than stopping on your own."
        ),
        question="Why might stopping an antibiotic early be a problem? (One reason)",
        accepted_keyword_sets=[["come", "back"], ["relapse"], ["resistance"], ["bacteria", "survive"], ["not", "fully"]],
        remediation_lesson="Stopping early can let bacteria survive and symptoms return; it can contribute to resistance.",
    ),
    Objective(
        oid="P1",
        category="Procedures",
        objective_text="Know it can often be taken with food if stomach upset happens.",
        lesson_text=(
            "Some people get an upset stomach with antibiotics.\n\n"
            "Taking the medication with food may help reduce this.\n\n"
            "Always follow the prescription directions if they specify otherwise."
        ),
        question="If amoxicillin upsets your stomach, what is one general strategy that may help?",
        accepted_keyword_sets=[["with", "food"], ["take", "food"], ["meal"], ["eat"], ["food", "help"], ["food"]],
        remediation_lesson="Tip: Many people tolerate antibiotics better with food. Follow your label.",
    ),
    Objective(
        oid="P2",
        category="Procedures",
        objective_text="Know to follow administration directions and keep a consistent schedule.",
        lesson_text=(
            "Try to take doses at roughly consistent times.\n\n"
            "Use reminders (alarm/calendar) and follow the label.\n\n"
            "If you’re unsure about timing, ask a pharmacist."
        ),
        question="What is a good habit for taking antibiotic doses over several days?",
        accepted_keyword_sets=[["consistent"], ["same", "time"], ["reminder"], ["schedule"]],
        remediation_lesson="Consistency helps: take doses around the same times and use reminders.",
    ),
    Objective(
        oid="P3",
        category="Procedures",
        objective_text="Know when to seek help (severe diarrhea, allergy signs, etc.).",
        lesson_text=(
            "Contact a clinician for severe/persistent diarrhea, severe rash, or allergy signs.\n\n"
            "Trouble breathing, swelling, or widespread hives can be urgent.\n\n"
            "This is general education—follow medical advice for your situation."
        ),
        question="Name ONE situation where you should contact a clinician promptly while on amoxicillin.",
        accepted_keyword_sets=[["severe", "diarrhea"], ["trouble", "breathing"], ["swelling"], ["hives"], ["severe", "rash"]],
        remediation_lesson="Prompt help: severe diarrhea, severe rash, hives/swelling, breathing trouble.",
    ),
    Objective(
        oid="R1",
        category="Rationales",
        objective_text="Explain a simple mechanism: interferes with bacterial cell wall building.",
        lesson_text=(
            "Amoxicillin is a beta-lactam antibiotic.\n\n"
            "In simple terms: it interferes with how bacteria build/maintain their cell walls.\n\n"
            "Without a stable cell wall, bacteria may not survive."
        ),
        question="In simple terms, how does amoxicillin affect bacteria?",
        accepted_keyword_sets=[["cell", "wall"], ["build", "wall"], ["bacterial", "wall"]],
        remediation_lesson="Mechanism shortcut: it interferes with bacterial cell wall building/maintenance.",
    ),
    Objective(
        oid="R2",
        category="Rationales",
        objective_text="Explain why penicillin allergy matters.",
        lesson_text=(
            "Amoxicillin is in the penicillin family.\n\n"
            "Penicillin allergies can be serious for some people.\n\n"
            "If someone has had severe reactions/anaphylaxis to penicillins, clinicians usually avoid them."
        ),
        question="Why is a penicillin allergy important to mention before taking amoxicillin?",
        accepted_keyword_sets=[["allergic"], ["reaction"], ["serious"], ["anaphylaxis"]],
        remediation_lesson="Allergy matters because amoxicillin is penicillin-family and can trigger serious reactions.",
    ),
    Objective(
        oid="R3",
        category="Rationales",
        objective_text="Explain why 'consult clinician' warnings appear based on intake.",
        lesson_text=(
            "Intake questions can flag potential contraindications or interactions.\n\n"
            "Instead of giving personalized medical instructions, a safe system shows warnings and recommends consulting a clinician.\n\n"
            "This reduces the chance of unsafe advice."
        ),
        question="Why does the system recommend 'consult a clinician' when it flags a warning?",
        accepted_keyword_sets=[["safety"], ["clinician"], ["not", "medical", "advice"], ["avoid", "liability"], ["personalized"]],
        remediation_lesson="Warnings trigger “consult clinician” because it’s safer than giving personalized medical advice.",
    ),
]

IBUPROFEN_OBJECTIVES: List[Objective] = [
    Objective(
        oid="F1",
        category="Facts",
        objective_text="Identify ibuprofen as a nonsteroidal anti-inflammatory drug.",
        lesson_text=(
            "Ibuprofen is a nonsteroidal anti-inflammatory drug, also called an NSAID.\n\n"
            "It is often used to help reduce pain, inflammation, and fever."
        ),
        question="What kind of medication is ibuprofen?",
        accepted_keyword_sets=[["nsaid"], ["anti", "inflammatory"], ["nonsteroidal"]],
        remediation_lesson="Ibuprofen is an NSAID used for pain, inflammation, and fever.",
    ),
    Objective(
        oid="D1",
        category="Dosage",
        objective_text="Know that ibuprofen dosage should follow the label or clinician instructions.",
        lesson_text=(
            "Ibuprofen dosage should follow the package label or clinician guidance.\n\n"
            "Do not take more than recommended, and ask a clinician if you are unsure."
        ),
        question="Should you take more ibuprofen than the label recommends?",
        accepted_keyword_sets=[["no"], ["not"], ["do", "not"]],
        remediation_lesson="Follow the label or clinician guidance and do not exceed the recommended dose.",
    ),
    Objective(
        oid="P1",
        category="Procedures",
        objective_text="Know that taking ibuprofen with food may help reduce stomach upset.",
        lesson_text=(
            "Some people take ibuprofen with food or milk to help reduce stomach upset.\n\n"
            "Always follow the directions on the label."
        ),
        question="What may help if ibuprofen causes stomach upset?",
        accepted_keyword_sets=[["food"], ["milk"], ["with", "food"]],
        remediation_lesson="Taking ibuprofen with food or milk may help with stomach upset.",
    ),
    Objective(
        oid="R1",
        category="Rationales",
        objective_text="Explain that ibuprofen works by reducing substances involved in inflammation and pain.",
        lesson_text=(
            "In simple terms, ibuprofen works by reducing substances in the body that contribute to pain, inflammation, and fever."
        ),
        question="How does ibuprofen work in simple terms?",
        accepted_keyword_sets=[["pain"], ["inflammation"], ["reducing"]],
        remediation_lesson="Ibuprofen works by reducing substances involved in pain and inflammation.",
    ),
]

DRUG_DATABASE = {
    "amoxicillin": {
        "display_name": "Amoxicillin",
        "objectives": AMOXICILLIN_OBJECTIVES,
    },
    "ibuprofen": {
        "display_name": "Ibuprofen",
        "objectives": IBUPROFEN_OBJECTIVES,
    },
}
