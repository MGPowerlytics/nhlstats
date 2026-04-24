from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from pathlib import Path


def test_key_loading():
    kalshkey_file = Path("kalshkey")
    if not kalshkey_file.exists():
        print(f"❌ {kalshkey_file} not found")
        return
    content = kalshkey_file.read_text(encoding="utf-8")

    private_key_lines = []
    in_key = False
    for line in content.splitlines():
        if "-----BEGIN RSA PRIVATE KEY-----" in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if "-----END RSA PRIVATE KEY-----" in line:
            break

    if not private_key_lines:
        print("❌ Could not extract RSA private key from kalshkey")
        return

    key_data = "\n".join(private_key_lines).encode("utf-8")
    try:
        serialization.load_pem_private_key(
            key_data, password=None, backend=default_backend()
        )
        print("✅ Key loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load key: {e}")


if __name__ == "__main__":
    test_key_loading()
