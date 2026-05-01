import requests
import json

SERVER_URL = "http://rcc-erp.dyndns.org:8081"
USERNAME   = "IT-Tech"
PASSWORD   = "bio@alfa99"

# Get token
resp  = requests.post(f"{SERVER_URL}/jwt-api-token-auth/",
        json={"username": USERNAME, "password": PASSWORD}, timeout=30)
token = resp.json().get("token")

# Fetch YOUR punches for April 15
headers = {"Content-Type": "application/json", "Authorization": f"JWT {token}"}
resp = requests.get(
    f"{SERVER_URL}/iclock/api/transactions/",
    headers=headers,
    params={
        "emp_code":   "000002721",
        "start_time": "2026-04-15 00:00:00",
        "end_time":   "2026-04-15 23:59:59",
        "page_size":  100,
    },
    timeout=30
)
data = resp.json()
for r in data.get("data", []):
    print(r.get("emp_code"), r.get("punch_time"), r.get("punch_type"))
