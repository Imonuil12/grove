from encryption import decrypt_data, decrypt_json, encrypt_data, encrypt_json


def test_round_trip_and_ciphertext_hides_text():
    secret = "Read 10 pages after coffee"
    token = encrypt_data(secret)
    assert secret not in token and decrypt_data(token) == secret
    assert decrypt_json(encrypt_json({"weight_kg": 80})) == {"weight_kg": 80}
