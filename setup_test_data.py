import requests
import json

URL_BASE = "http://localhost:9000"

def setup():
    # 1. Register a customer
    print("Registering customer...")
    auth_data = {
        "email": "testuser_lex@ecomoi.local",
        "password": "password123",
        "first_name": "Test",
        "last_name": "User"
    }
    # For Medusa V2, usually /auth/customer/emailpass/register
    try:
        r = requests.post(f"{URL_BASE}/auth/customer/emailpass/register", json=auth_data)
        if r.status_code == 200:
            token = r.json().get("token")
            print(f"Registered. Token: {token[:10]}...")
            return token
        else:
            print(f"Failed to register. {r.status_code} {r.text}")
            
            # try login if already exists
            r2 = requests.post(f"{URL_BASE}/auth/customer/emailpass", json={"email": auth_data["email"], "password": auth_data["password"]})
            if r2.status_code == 200:
                token = r2.json().get("token")
                print(f"Logged in. Token: {token[:10]}...")
                return token
            else:
                print(f"Failed to login. {r2.status_code} {r2.text}")
                return None
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    setup()
