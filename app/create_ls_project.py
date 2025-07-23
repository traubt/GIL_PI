import requests
import json
from datetime import datetime, timedelta, timezone

API_URL = "https://api.lsk.lightspeed.app/o/op/1/order/toGo"
ACCESS_TOKEN = "d03f8f2e-67df-4210-b388-8011be9e7bf6"

def get_lightspeed_timestamp():
    tz = timezone(timedelta(hours=2))
    now = datetime.now(tz).replace(microsecond=0)
    return now.isoformat(timespec="seconds")



def create_order(order_data):
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(API_URL, headers=headers, json=order_data)

    if response.status_code == 200:
        print("✅ Order created successfully!")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ Failed to create order. Status Code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    tz = timezone(timedelta(hours=2))  # South Africa
    # timestamp = get_lightspeed_timestamp()
    # timestamp = "2025-06-18T10:00:00+02:00"
    timestamp = "2025-06-18T08:00:00Z"
    print(f"Using timestamp: {timestamp}")

    order_body = {
            "businessLocationId": "195051644848426",
            "thirdPartyReference": "tomer test 9",
            "endpointId": "TEST",
            "customerInfo": {
                "firstName": "Tomer",
                "lastName": "Traub",
                "email": "tomer.traub@gmail.com",
                "contactNumberAsE164": "+2723456789"
            },
            "deliveryAddress": {
                "addressLine1": "test@gmail.com",
                "addressLine2": "Addressline2"
            },
            "accountProfileCode": "ONLINE",
            "payment": {
                "paymentMethod": "Online",
                "paymentAmount": "225.00"
            },
            "orderNote": "LOCAL PICKUP",
            "tableNumber": 1,
            "items": [
                {
                    "quantity": 1,
                    "sku": "BUD004",
                    "subItems": []
                },
                {
                    "quantity": 1,
                    "sku": "FT2",
                    "customItemName": "Payfast Transaction ID : 123456",
                    "subItems": []
                }
            ]
    }

    create_order(order_body)