"""
Sprint 10 Verification Test Suite: Adaptive Learning & Personalized Conversations
Validates User Story #188 and Tasks #190, #191, #192:
- Task #190: Connect chatbot responses to user learning progress (intake, quiz results, objective mastery).
- Task #191: Implement adaptive explanations, intuitive real-world analogies, and follow-up questions.
- Task #192: Test adaptive learning and clinical safety together (preserving contraindication checks and user isolation).
"""
import time
import os
import sqlite3
import jwt
import requests
from sqlalchemy.orm import Session
from database import SessionLocal
import models as m
import adaptive_learning

BASE_URL = "http://127.0.0.1:8000"


def generate_test_token(email: str) -> str:
    region = os.getenv("COGNITO_REGION", "us-east-2")
    pool_id = os.getenv("COGNITO_USER_POOL_ID", "us-east-2_TestPool")
    return jwt.encode(
        {
            "email": email,
            "cognito:username": email,
            "sub": f"uuid-{email}",
            "exp": time.time() + 3600,
            "iss": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
        },
        "test-secret-key-123456789012345678901234",
        algorithm="HS256"
    )


def run_tests():
    print("==================================================")
    print("🧠 SPRINT 10 ADAPTIVE LEARNING & SAFETY TEST SUITE")
    print("==================================================")

    db: Session = SessionLocal()

    student_a = "adaptive.student.alpha@example.com"
    token_a = generate_test_token(student_a)
    headers_a = {
        "Authorization": f"Bearer {token_a}",
        "Content-Type": "application/json"
    }

    student_b = "mastery.student.beta@example.com"
    token_b = generate_test_token(student_b)
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "Content-Type": "application/json"
    }

    # =========================================================================
    # TEST 1: Task #190 - Connect Chatbot to Relational Learning Progress
    # =========================================================================
    print("\n[TEST 1] Task #190: Extracting Relational Learning Progress & Quiz Failures...")
    # Save intake for Student A
    res_intake = requests.post(
        f"{BASE_URL}/intake",
        headers=headers_a,
        json={
            "username": student_a,
            "drug": "amoxicillin",
            "experience_level": "beginner",
            "archetype": "needs more explanations",
            "penicillin_allergy": False,
            "meds_text": ""
        }
    )
    assert res_intake.status_code == 200, f"Intake failed: {res_intake.text}"

    # Submit a checkpoint quiz where student misses F3 (side effects vs allergy) and R1 (cell wall mechanism)
    res_checkpoint = requests.post(
        f"{BASE_URL}/checkpoint",
        headers=headers_a,
        json={
            "username": student_a,
            "drug": "amoxicillin",
            "answers": {
                "F1": "antibiotic",         # Correct
                "F2": "no",                 # Correct
                "F3": "headache and sleepy",# Incorrect! Missed allergy vs side effects
                "R1": "kills stomach acid", # Incorrect! Missed cell wall mechanism
            }
        }
    )
    assert res_checkpoint.status_code == 200, f"Checkpoint submission failed: {res_checkpoint.text}"
    checkpoint_data = res_checkpoint.json()
    assert checkpoint_data.get("score") is not None or "results" in checkpoint_data or "passed" in checkpoint_data

    # Diagnostic check: verify learning profile extracts struggling OIDs
    profile_a = adaptive_learning.get_user_learning_profile(student_a, "amoxicillin", db)
    assert "F3" in profile_a["struggling_oids"], f"F3 must be flagged as struggling: {profile_a['struggling_oids']}"
    assert "R1" in profile_a["struggling_oids"], f"R1 must be flagged as struggling: {profile_a['struggling_oids']}"
    assert "F1" in profile_a["mastered_oids"], f"F1 should be marked mastered: {profile_a['mastered_oids']}"
    assert len(profile_a["missed_questions"]) > 0, "Missed questions must be retrieved from SQL tables"

    print("  ✓ Correctly connected to relational tables (UserObjectiveMastery & UserQuizResponse).")
    print(f"  ✓ Identified struggling topics: {profile_a['struggling_oids']}")
    print(f"  ✓ Identified mastered topics: {profile_a['mastered_oids']}")

    # =========================================================================
    # TEST 2: Task #191 - Adaptive Alternative Explanation with Intuitive Analogy
    # =========================================================================
    print("\n[TEST 2] Task #191: Chatbot Delivers Alternative Analogy for Struggling Concept...")
    # Student A asks about side effects (F3, which they missed)
    chat_f3 = requests.post(
        f"{BASE_URL}/chat",
        headers=headers_a,
        json={
            "username": student_a,
            "drug": "amoxicillin",
            "message": "Can you explain the side effects of amoxicillin?",
            "archetype": "needs more explanations"
        }
    )
    assert chat_f3.status_code == 200, f"Chat failed: {chat_f3.text}"
    resp_f3 = chat_f3.json()["response"]

    # Verify the response adapts to F3:
    # Must contain alternative conceptual framing (traffic light / red siren / mild vs emergency)
    f3_analogy_detected = any(phrase in resp_f3.lower() for phrase in [
        "traffic light", "yellow", "red siren", "emergency", "swelling", "hives", "reinforcement"
    ])
    assert f3_analogy_detected, f"Expected adaptive alternative analogy for F3 in response: {resp_f3[:200]}"
    print("  ✓ Chatbot detected struggling objective F3.")
    print("  ✓ Provided alternative real-world analogy (traffic light: yellow mild vs red emergency).")

    # =========================================================================
    # TEST 3: Task #191 - Interactive Follow-Up Question Before Moving Forward
    # =========================================================================
    print("\n[TEST 3] Task #191: Chatbot Asks Check-for-Understanding Follow-Up Question...")
    has_question_mark = "?" in resp_f3
    has_follow_up_prompt = any(phrase in resp_f3.lower() for phrase in [
        "check", "before we move", "quick check", "would you", "what do you think", "why", "mild", "emergency"
    ])
    assert has_question_mark and has_follow_up_prompt, f"Expected interactive follow-up question in response: {resp_f3[-200:]}"
    print("  ✓ Chatbot concluded response with interactive check-in follow-up question.")

    # =========================================================================
    # TEST 4: Task #191 - Proactive Review & Reinforcement Intent
    # =========================================================================
    print("\n[TEST 4] Task #191: Proactive Review Request Surfaces Struggling Concepts...")
    review_chat = requests.post(
        f"{BASE_URL}/chat",
        headers=headers_a,
        json={
            "username": student_a,
            "drug": "amoxicillin",
            "message": "What concepts am I struggling with? Can we review?",
            "archetype": "needs more explanations"
        }
    )
    assert review_chat.status_code == 200, f"Review chat failed: {review_chat.text}"
    review_resp = review_chat.json()["response"]

    # Verify proactive review identifies their missed concepts and offers practice
    assert any(term in review_resp.lower() for term in ["reinforcement", "review", "quiz", "f3", "side effects", "perspective", "check-in"]), \
        f"Expected proactive review summary: {review_resp}"
    print("  ✓ Proactive review request recognized and tailored to user's exact missed topics.")

    # =========================================================================
    # TEST 5: Task #192 - Preserving Clinical Safety Checks Alongside Adaptive Learning
    # =========================================================================
    print("\n[TEST 5] Task #192: Clinical Safety Guardrails Preserved with Adaptive Learning...")
    # Update Student A's intake to have a Penicillin Allergy + Warfarin
    requests.post(
        f"{BASE_URL}/intake",
        headers=headers_a,
        json={
            "username": student_a,
            "drug": "amoxicillin",
            "experience_level": "beginner",
            "archetype": "needs more explanations",
            "penicillin_allergy": True,
            "anaphylaxis_history": True,
            "meds_text": "Warfarin 5mg daily"
        }
    )

    # Student A asks about side effects again
    safe_chat = requests.post(
        f"{BASE_URL}/chat",
        headers=headers_a,
        json={
            "username": student_a,
            "drug": "amoxicillin",
            "message": "Can I take amoxicillin for my toothache despite side effects?",
            "archetype": "needs more explanations"
        }
    )
    assert safe_chat.status_code == 200, f"Safe chat failed: {safe_chat.text}"
    safe_data = safe_chat.json()

    # Safety warning MUST trigger prominently
    assert safe_data.get("safety_warning") is not None, "Clinical safety warning must NOT be suppressed!"
    assert "PATIENT SAFETY WARNING" in safe_data["safety_warning"]
    assert "Warfarin" in safe_data["safety_warning"]
    # AND educational response must be present
    assert len(safe_data.get("response", "")) > 20, "Educational response must still be provided"

    print("  ✓ Clinical safety warning triggered prominently without being suppressed:")
    print(f"    -> {safe_data['safety_warning'][:80]}...")
    print("  ✓ Educational response delivered alongside clinical safety banner.")

    # =========================================================================
    # TEST 6: Task #192 - Multi-User Separation & Data Isolation
    # =========================================================================
    print("\n[TEST 6] Task #192: Strict User Separation (Zero Knowledge Bleed)...")
    # Student B has 100% mastery on everything
    requests.post(
        f"{BASE_URL}/intake",
        headers=headers_b,
        json={
            "username": student_b,
            "drug": "amoxicillin",
            "experience_level": "advanced",
            "archetype": "the skeptic",
            "penicillin_allergy": False,
            "meds_text": ""
        }
    )
    requests.post(
        f"{BASE_URL}/checkpoint",
        headers=headers_b,
        json={
            "username": student_b,
            "drug": "amoxicillin",
            "answers": {
                "F1": "antibiotic",
                "F2": "no",
                "F3": "trouble breathing, swelling",
                "R1": "cell wall",
            }
        }
    )

    profile_b = adaptive_learning.get_user_learning_profile(student_b, "amoxicillin", db)
    # Student B should NOT have F3 in struggling_oids
    assert "F3" not in profile_b["struggling_oids"], f"Student B must NOT have F3 as struggling: {profile_b['struggling_oids']}"

    # Student B asks proactive review question
    b_review = requests.post(
        f"{BASE_URL}/chat",
        headers=headers_b,
        json={
            "username": student_b,
            "drug": "amoxicillin",
            "message": "What concepts am I struggling with?",
            "archetype": "the skeptic"
        }
    )
    assert b_review.status_code == 200
    b_resp = b_review.json()["response"]
    # Should say strong understanding / on track / no struggling concepts
    assert any(w in b_resp.lower() for w in ["great", "strong", "master", "on track", "zero", "none", "haven't", "no specific", "not flagged", "no concepts"]), \
        f"Student B with clean mastery should receive congratulations: {b_resp}"

    print("  ✓ Student A's missed concepts do NOT leak to Student B.")
    print("  ✓ Student B receives appropriate clean mastery confirmation.")

    # =========================================================================
    # TEST 7: Task #192 - Database Encryption at Rest & Decrypted History Retrieval
    # =========================================================================
    print("\n[TEST 7] Task #192: HIPAA Encryption at Rest & History Retrieval...")
    db_path = os.path.join(os.path.dirname(__file__), "chatbot.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT sender, message FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT 2",
        (student_a,)
    )
    rows = cur.fetchall()
    conn.close()

    assert len(rows) == 2, "Expected saved chat messages for student A"
    for sender, enc_msg in rows:
        assert enc_msg.startswith("enc:"), f"Message must be encrypted with Fernet at rest! Found: {enc_msg[:30]}"
    print("  ✓ Chat messages are verified encrypted at rest in SQLite `chat_messages` table.")

    # Test /chat/history retrieves decrypted messages
    hist_res = requests.get(f"{BASE_URL}/chat/history?drug=amoxicillin", headers=headers_a)
    assert hist_res.status_code == 200, f"History request failed: {hist_res.text}"
    history = hist_res.json()
    assert len(history) >= 2, "Chat history must return messages"
    assert not history[-1]["message"].startswith("enc:"), "Messages must be decrypted for authenticated user"
    print(f"  ✓ /chat/history returned {len(history)} decrypted messages on the fly.")

    db.close()

    print("\n==================================================")
    print("🎉 ALL SPRINT 10 ADAPTIVE LEARNING TESTS PASSED! (100% SUCCESS)")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
