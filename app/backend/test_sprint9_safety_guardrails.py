import time
import jwt
import requests
import sqlite3
import json
import os
import sys

BASE_URL = "http://127.0.0.1:8000"

def generate_test_token(email: str) -> str:
    return jwt.encode(
        {
            "email": email,
            "cognito:username": email,
            "sub": "user-uuid-sprint9-safety",
            "exp": time.time() + 3600,
            "iss": f"https://cognito-idp.{os.getenv('COGNITO_REGION', 'us-east-2')}.amazonaws.com/{os.getenv('COGNITO_USER_POOL_ID', 'us-east-2_TestPool')}"
        },
        "test-secret-key-123456789012345678901234",
        algorithm="HS256"
    )

def run_tests():
    print("==================================================")
    print("🛡️ SPRINT 9 CLINICAL SAFETY GUARDRAILS TEST SUITE")
    print("==================================================")

    test_user = "clinical.test.patient@example.com"
    token = generate_test_token(test_user)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Helper to send chat message
    def send_chat(drug: str, message: str):
        t0 = time.time()
        res = requests.post(
            f"{BASE_URL}/chat",
            headers=headers,
            json={
                "username": test_user,
                "drug": drug,
                "message": message,
                "archetype": "Needs more explanations"
            }
        )
        elapsed = time.time() - t0
        assert res.status_code == 200, f"Chat failed with status {res.status_code}: {res.text}"
        data = res.json()
        assert elapsed < 10.0, f"Response latency exceeded 10.0s ({elapsed:.2f}s)"
        return data, elapsed

    # Scenario 1: Penicillin Allergy & Anaphylaxis Guardrail
    print("\n[SCENARIO 1] Penicillin Allergy & Anaphylaxis Guardrail...")
    requests.post(
        f"{BASE_URL}/intake",
        headers=headers,
        json={
            "username": test_user,
            "drug": "amoxicillin",
            "penicillin_allergy": True,
            "anaphylaxis_history": True,
            "meds_text": ""
        }
    )
    data, lat = send_chat("amoxicillin", "Can I take amoxicillin for a severe toothache?")
    assert data.get("safety_warning") is not None, "Penicillin allergy warning MUST trigger"
    assert "Penicillin allergy / Anaphylaxis" in data["safety_warning"]
    print(f"  ✓ Flagged correctly in {lat:.3f}s: {data['safety_warning'][:70]}...")

    # Scenario 2: Mononucleosis Advisory Guardrail
    print("\n[SCENARIO 2] Mononucleosis Maculopapular Rash Advisory...")
    requests.post(
        f"{BASE_URL}/intake",
        headers=headers,
        json={
            "username": test_user,
            "drug": "amoxicillin",
            "penicillin_allergy": False,
            "mono_suspected": True,
            "meds_text": ""
        }
    )
    data, lat = send_chat("amoxicillin", "I have a sore throat, can I take amoxicillin?")
    assert data.get("safety_warning") is not None, "Mono advisory MUST trigger"
    assert "Mononucleosis" in data["safety_warning"]
    print(f"  ✓ Flagged correctly in {lat:.3f}s: {data['safety_warning'][:70]}...")

    # Scenario 3: Chronic Kidney Disease & NSAID (Ibuprofen) Contraindication
    print("\n[SCENARIO 3] Kidney Disease & Ibuprofen Contraindication...")
    requests.post(
        f"{BASE_URL}/intake",
        headers=headers,
        json={
            "username": test_user,
            "drug": "ibuprofen",
            "kidney_disease": True,
            "meds_text": ""
        }
    )
    data, lat = send_chat("ibuprofen", "Can I take ibuprofen 600mg for joint pain?")
    assert data.get("safety_warning") is not None, "Kidney disease contraindication MUST trigger"
    assert "Kidney disease flagged" in data["safety_warning"]
    assert "NSAIDs like Ibuprofen" in data["safety_warning"]
    print(f"  ✓ Flagged correctly in {lat:.3f}s: {data['safety_warning'][:70]}...")

    # Scenario 4: Warfarin + Amoxicillin Interaction (INR Elevation)
    print("\n[SCENARIO 4] Warfarin + Amoxicillin Drug-Drug Interaction...")
    requests.post(
        f"{BASE_URL}/intake",
        headers=headers,
        json={
            "username": test_user,
            "drug": "amoxicillin",
            "kidney_disease": False,
            "meds_text": "Warfarin 5mg daily"
        }
    )
    data, lat = send_chat("amoxicillin", "Will amoxicillin affect my current medications?")
    assert data.get("safety_warning") is not None, "Warfarin interaction MUST trigger"
    assert "Warfarin listed" in data["safety_warning"]
    assert "INR" in data["safety_warning"]
    print(f"  ✓ Flagged correctly in {lat:.3f}s: {data['safety_warning'][:70]}...")

    # Scenario 5: Warfarin + Ibuprofen Critical Interaction (Gastrointestinal Hemorrhage)
    print("\n[SCENARIO 5] Warfarin + Ibuprofen Critical Interaction...")
    requests.post(
        f"{BASE_URL}/intake",
        headers=headers,
        json={
            "username": test_user,
            "drug": "ibuprofen",
            "meds_text": "Coumadin / Warfarin"
        }
    )
    data, lat = send_chat("ibuprofen", "Can I take ibuprofen while taking warfarin?")
    assert data.get("safety_warning") is not None, "Warfarin + Ibuprofen critical interaction MUST trigger"
    assert "CRITICAL DRUG INTERACTION" in data["safety_warning"]
    assert "hemorrhage" in data["safety_warning"].lower() or "bleeding" in data["safety_warning"].lower()
    print(f"  ✓ Flagged correctly in {lat:.3f}s: {data['safety_warning'][:70]}...")

    # Scenario 6: Methotrexate + Amoxicillin Interaction (Renal Clearance Impairment)
    print("\n[SCENARIO 6] Methotrexate + Amoxicillin Toxicity Interaction...")
    requests.post(
        f"{BASE_URL}/intake",
        headers=headers,
        json={
            "username": test_user,
            "drug": "amoxicillin",
            "meds_text": "Methotrexate 15mg weekly for rheumatoid arthritis"
        }
    )
    data, lat = send_chat("amoxicillin", "Is amoxicillin safe with my arthritis medicine?")
    assert data.get("safety_warning") is not None, "Methotrexate interaction MUST trigger"
    assert "Methotrexate" in data["safety_warning"]
    print(f"  ✓ Flagged correctly in {lat:.3f}s: {data['safety_warning'][:70]}...")

    # Scenario 7: Aspirin + Ibuprofen Interaction (Cardioprotection Blunting)
    print("\n[SCENARIO 7] Aspirin + Ibuprofen Antiplatelet Interference...")
    requests.post(
        f"{BASE_URL}/intake",
        headers=headers,
        json={
            "username": test_user,
            "drug": "ibuprofen",
            "meds_text": "Baby Aspirin 81mg"
        }
    )
    data, lat = send_chat("ibuprofen", "Can I take ibuprofen with my daily aspirin?")
    assert data.get("safety_warning") is not None, "Aspirin + Ibuprofen interaction MUST trigger"
    assert "Aspirin" in data["safety_warning"]
    print(f"  ✓ Flagged correctly in {lat:.3f}s: {data['safety_warning'][:70]}...")

    # Scenario 8: Pregnancy 3rd Trimester Contraindication with Ibuprofen
    print("\n[SCENARIO 8] Pregnancy 3rd Trimester & Ibuprofen Contraindication...")
    requests.post(
        f"{BASE_URL}/intake",
        headers=headers,
        json={
            "username": test_user,
            "drug": "ibuprofen",
            "pregnancy_status": "3rd trimester",
            "meds_text": ""
        }
    )
    data, lat = send_chat("ibuprofen", "I have a headache, is ibuprofen safe during pregnancy?")
    assert data.get("safety_warning") is not None, "Pregnancy warning MUST trigger"
    assert "PREGNANCY WARNING" in data["safety_warning"]
    assert "ductus arteriosus" in data["safety_warning"].lower()
    print(f"  ✓ Flagged correctly in {lat:.3f}s: {data['safety_warning'][:70]}...")

    # Scenario 9: Chat History Persistence & HIPAA Data-at-Rest Encryption
    print("\n[SCENARIO 9] Chat History DB Verification & Encryption at Rest...")
    db_path = os.path.join(os.path.dirname(__file__), "chatbot.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT sender, message, has_safety_warning FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT 2",
        (test_user,)
    )
    rows = cur.fetchall()
    conn.close()

    assert len(rows) >= 2, "Expected saved chat messages in database"
    last_bot_sender, last_bot_msg, last_bot_warning = rows[0]
    last_user_sender, last_user_msg, _ = rows[1]

    assert last_bot_sender == "bot"
    assert last_user_sender == "user"
    assert last_bot_warning == 1 or last_bot_warning is True, "Database record must retain has_safety_warning=True"
    assert last_bot_msg.startswith("enc:"), "Bot message in SQLite must be encrypted at rest (enc:...)"
    assert last_user_msg.startswith("enc:"), "User message in SQLite must be encrypted at rest (enc:...)"
    print("  ✓ Messages saved in `chat_messages` table with has_safety_warning=True.")
    print(f"  ✓ HIPAA encryption confirmed: {last_bot_msg[:45]}... [ENCRYPTED]")

    # Scenario 10: /chat/history Endpoint Verification
    print("\n[SCENARIO 10] /chat/history Endpoint Decryption & Retrieval...")
    hist_res = requests.get(f"{BASE_URL}/chat/history?drug=ibuprofen", headers=headers)
    assert hist_res.status_code == 200, f"History failed: {hist_res.status_code}"
    history = hist_res.json()
    assert len(history) > 0, "Chat history must return messages"
    last_item = history[-1]
    assert not last_item["message"].startswith("enc:"), "Messages must be automatically decrypted for client"
    assert last_item["has_safety_warning"] is True, "Decrypted item must retain safety warning flag"
    print(f"  ✓ Decrypted {len(history)} messages on the fly. Last message: '{last_item['message'][:50]}...'")

    print("\n==================================================")
    print("🎉 ALL 10 SPRINT 9 CLINICAL SAFETY TESTS PASSED! (100% SUCCESS)")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
