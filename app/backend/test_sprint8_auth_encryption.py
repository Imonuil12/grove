import time
import jwt
import requests
import sqlite3
import json
import os
from encryption import encrypt_data, decrypt_data, encrypt_json, decrypt_json

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("==================================================")
    print("🚀 SPRINT 8 TASK VERIFICATION TEST SUITE")
    print("==================================================")

    # 1. Test Encryption Unit Logic
    print("\n[TEST 1] Testing Session Encryption & Decryption at Rest...")
    sample_intake = {
        "selected_drug": "amoxicillin",
        "archetype": "Needs more explanations",
        "intake": {
            "penicillin_allergy": True,
            "meds_text": "Warfarin 5mg daily, Lisinopril 10mg"
        }
    }
    encrypted_blob = encrypt_json(sample_intake)
    assert encrypted_blob.startswith("enc:"), "Ciphertext must be prefixed with 'enc:'"
    assert "Warfarin" not in encrypted_blob, "Sensitive health data must NOT appear in plaintext!"
    
    decrypted_blob = decrypt_json(encrypted_blob)
    assert decrypted_blob["intake"]["meds_text"] == "Warfarin 5mg daily, Lisinopril 10mg"
    print("  ✓ Encrypted session payload securely obscured at rest.")
    print("  ✓ Decrypted payload matches original patient profile exactly.")

    # 2. Test JWT Generation & /auth/verify endpoint
    print("\n[TEST 2] Testing JWT Verification via /auth/verify Endpoint...")
    demo_email = "test.verified.user@example.com"
    valid_token = jwt.encode(
        {
            "email": demo_email,
            "cognito:username": demo_email,
            "sub": "user-uuid-98765",
            "exp": time.time() + 3600,
            "iss": f"https://cognito-idp.{os.getenv('COGNITO_REGION', 'us-east-2')}.amazonaws.com/{os.getenv('COGNITO_USER_POOL_ID', 'us-east-2_TestPool')}"
        },
        "test-secret-key-123456789012345678901234",
        algorithm="HS256"
    )

    # Test without token -> should fail on strict /auth/verify
    res_no_auth = requests.get(f"{BASE_URL}/auth/verify")
    assert res_no_auth.status_code == 401, f"Expected 401 Unauthorized, got {res_no_auth.status_code}"
    print("  ✓ Missing token correctly rejected with 401 Unauthorized.")

    # Test with valid Bearer token -> should succeed
    res_auth = requests.get(
        f"{BASE_URL}/auth/verify",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert res_auth.status_code == 200, f"Expected 200 OK, got {res_auth.status_code}: {res_auth.text}"
    auth_data = res_auth.json()
    assert auth_data["authenticated"] is True
    assert auth_data["email"] == demo_email
    print(f"  ✓ Valid JWT token accepted. Authenticated identity: {auth_data['email']}")

    # 3. Test Protected Endpoint with JWT (/chat and intake)
    print("\n[TEST 3] Testing Patient Intake & Chat with JWT Authentication...")
    intake_res = requests.post(
        f"{BASE_URL}/intake",
        headers={
            "Authorization": f"Bearer {valid_token}",
            "Content-Type": "application/json"
        },
        json={
            "username": demo_email,
            "drug": "amoxicillin",
            "penicillin_allergy": True,
            "anaphylaxis_history": True,
            "meds_text": "Warfarin"
        }
    )
    assert intake_res.status_code == 200, f"Intake save failed: {intake_res.status_code}"
    intake_data = intake_res.json()
    print("  ✓ Intake saved successfully with warnings:", intake_data.get("warnings"))

    chat_res = requests.post(
        f"{BASE_URL}/chat",
        headers={
            "Authorization": f"Bearer {valid_token}",
            "Content-Type": "application/json"
        },
        json={
            "username": demo_email,
            "drug": "amoxicillin",
            "message": "Can I take amoxicillin for my toothache?",
            "archetype": "Needs more explanations"
        }
    )
    assert chat_res.status_code == 200, f"Chat failed: {chat_res.status_code}"
    chat_data = chat_res.json()
    assert chat_data.get("safety_warning") is not None, "Clinical safety warning must be triggered!"
    print("  ✓ Chat response generated with clinical safety warning banner:")
    print("    ->", chat_data["safety_warning"])

    # 4. Verify relational intake persistence and encrypted chat history.
    # profile_data is deliberately unused after the relational conversion.
    print("\n[TEST 4] Inspecting relational intake and encrypted chat history...")
    db_path = os.path.join(os.path.dirname(__file__), "chatbot.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT email, profile_data FROM users WHERE email = ?", (demo_email,))
    row = cur.fetchone()
    assert row is not None, "User record must exist in SQLite database"
    assert row[1] == "{}", "Legacy profile_data must not store current learning state"
    cur.execute(
        "SELECT i.penicillin_allergy, i.meds_text FROM user_intakes i "
        "JOIN user_learning_state s ON s.latest_intake_id = i.intake_id "
        "JOIN users u ON s.user_id = u.id WHERE u.email = ?", (demo_email,)
    )
    intake_row = cur.fetchone()
    assert intake_row and intake_row[0] and intake_row[1] == "Warfarin"
    cur.execute("SELECT message FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT 2", (demo_email,))
    messages = cur.fetchall()
    assert len(messages) == 2 and all(message[0].startswith("enc:") for message in messages)
    print("  ✓ Intake saved in relational rows; legacy JSON remains unused.")
    print("  ✓ User and bot chat messages are encrypted at rest.")
    conn.close()

    print("\n==================================================")
    print("🎉 ALL SPRINT 8 TASKS VERIFIED & WORKING PERFECTLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
