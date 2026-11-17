import os
import json
from cryptography.fernet import Fernet
import env_config  # noqa: F401


# Key should be a 32 url-safe base64-encoded bytes string
DEFAULT_KEY = b"3W0RlkTnG2TkDi_FMr-U0BICEeDqSyHXenQoByAuw2g="
RAW_KEY = os.getenv("SESSION_ENCRYPTION_KEY")

if RAW_KEY:
    try:
        ENCRYPTION_KEY = RAW_KEY.encode("utf-8")
        _cipher = Fernet(ENCRYPTION_KEY)
    except Exception:
        # Not a Fernet key (e.g. a host-generated random secret): derive one from it.
        import base64, hashlib
        ENCRYPTION_KEY = base64.urlsafe_b64encode(hashlib.sha256(RAW_KEY.encode("utf-8")).digest())
        _cipher = Fernet(ENCRYPTION_KEY)
else:
    ENCRYPTION_KEY = DEFAULT_KEY
    _cipher = Fernet(ENCRYPTION_KEY)

def encrypt_data(plain_text: str) -> str:
    """
    Encrypts a plaintext string and prefixes it with 'enc:'
    """
    if plain_text is None:
        return None
    if not isinstance(plain_text, str):
        plain_text = str(plain_text)
    encrypted_bytes = _cipher.encrypt(plain_text.encode("utf-8"))
    return "enc:" + encrypted_bytes.decode("utf-8")

def decrypt_data(cipher_text: str) -> str:
    """
    Decrypts an encrypted string. If the string is unencrypted
    (e.g. legacy plain JSON starting without 'enc:'), it returns the original string safely.
    """
    if cipher_text is None:
        return None
    if not isinstance(cipher_text, str):
        return str(cipher_text)
    
    if cipher_text.startswith("enc:"):
        token = cipher_text[4:].encode("utf-8")
        try:
            decrypted_bytes = _cipher.decrypt(token)
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            print(f"[Encryption Error] Failed to decrypt token: {e}")
            return "{}"
    return cipher_text

def encrypt_json(data: dict) -> str:
    """
    Serializes a dictionary to JSON and encrypts it.
    """
    return encrypt_data(json.dumps(data))

def decrypt_json(cipher_text: str) -> dict:
    """
    Decrypts and deserializes JSON. Handles legacy plain JSON automatically.
    """
    plain = decrypt_data(cipher_text)
    if not plain:
        return {}
    try:
        return json.loads(plain)
    except Exception as e:
        print(f"[JSON Error] Failed to parse decrypted JSON: {e}")
        return {}
