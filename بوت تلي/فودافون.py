import argparse
import getpass
import sys

import requests

CLIENT_SECRET = "95fd95fb-7489-4958-8ae6-d31a525cd20a"
CLIENT_ID = "ana-vodafone-app"
TOKEN_URL = "https://mobile.vodafone.com.eg/auth/realms/vf-realm/protocol/openid-connect/token"
OFFERING_URL = "https://mobile.vodafone.com.eg/services/dxl/epo/eligibleProductOffering"
ORDER_URL = "https://mobile.vodafone.com.eg/services/dxl/pom/productOrder"


def plus_login(number: str, password: str):
    """تسجيل الدخول والحصول على access token"""
    data = {
        "grant_type": "password",
        "username": number,
        "password": password,
        "client_secret": CLIENT_SECRET,
        "client_id": CLIENT_ID,
    }
    headers = {
        "User-Agent": "okhttp/4.12.0",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Connection": "Keep-Alive",
        "api-version": "v2",
        "device-id": "7be546fe335911d2",
        "x-agent-operatingsystem": "13",
        "clientId": "AnaVodafoneAndroid",
        "x-agent-device": "Samsung SM-A515F",
        "x-agent-version": "2025.11.1",
        "x-agent-build": "1063",
        "msisdn": number,
        "Accept-Language": "ar",
    }
    try:
        response = requests.post(TOKEN_URL, data=data, headers=headers, timeout=30)
        if response.status_code == 200:
            token_data = response.json()
            return {"success": True, "token": token_data.get("access_token")}
        return {"success": False, "message": f"الرقم أو كلمة المرور غير صحيحة (كود: {response.status_code})\n{response.text}"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


def get_plus_packages(token: str, phone: str):
    """جلب كل عروض MI المتاحة على الرقم"""
    headers = {
        "User-Agent": "okhttp/4.12.0",
        "Connection": "Keep-Alive",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "api-version": "v2",
        "device-id": "7be546fe335911d2",
        "x-agent-operatingsystem": "13",
        "clientId": "AnaVodafoneAndroid",
        "x-agent-device": "Samsung SM-A515F",
        "x-agent-version": "2025.11.1",
        "x-agent-build": "1063",
        "msisdn": phone,
        "Content-Type": "application/json",
        "Accept-Language": "ar",
    }
    params = {
        "customerAccountId": phone,
        "type": "MIProducts",
    }
    try:
        response = requests.get(OFFERING_URL, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def parse_plus_packages(data):
    """فلترة العروض للحصول على باقات Plus فقط"""
    if not data:
        return []

    plus_packages = []
    index = 1

    for item in data:
        if "parts" in item and "productOffering" in item["parts"]:
            offerings = item["parts"]["productOffering"]
            if not isinstance(offerings, list):
                offerings = [offerings]

            for offering in offerings:
                name = offering.get("name", "")

                if "بلص" in name or "Plus" in name or "plus" in name.lower():
                    package = {
                        "index": index,
                        "name": name,
                        "id": "",
                        "encProductId": "",
                        "price": 0,
                        "quota": "غير معروف",
                        "duration": "غير معروف",
                    }

                    id_list = offering.get("id", [])
                    if isinstance(id_list, list):
                        for id_item in id_list:
                            if id_item.get("schemeName") == "CommercialID":
                                package["id"] = id_item.get("value", "")
                            elif id_item.get("schemeName") == "EncProductID":
                                package["encProductId"] = id_item.get("value", "")

                    price_list = offering.get("price", [])
                    if isinstance(price_list, list):
                        for price_item in price_list:
                            if "originalPrice" in price_item and "value" in price_item["originalPrice"]:
                                package["price"] = price_item["originalPrice"]["value"]
                                break

                    spec = offering.get("specification", {})
                    char_list = spec.get("characteristicsValue", [])
                    if isinstance(char_list, list):
                        for char in char_list:
                            if char.get("characteristicName") == "QUOTA":
                                value = char.get("value", "")
                                unit = char.get("type", "MB")
                                package["quota"] = f"{value} {unit}"
                            elif char.get("characteristicName") == "DURATION":
                                package["duration"] = char.get("value", "غير معروف")

                    if package["price"] > 0:
                        plus_packages.append(package)
                        index += 1

    return plus_packages


def activate_plus_package(token: str, phone: str, package: dict):
    """تفعيل باقة Plus معينة"""
    headers = {
        "User-Agent": "okhttp/4.12.0",
        "Connection": "Keep-Alive",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "api-version": "v2",
        "device-id": "7be546fe335911d2",
        "x-agent-operatingsystem": "13",
        "clientId": "AnaVodafoneAndroid",
        "x-agent-device": "Samsung SM-A515F",
        "x-agent-version": "2025.11.1",
        "x-agent-build": "1063",
        "msisdn": phone,
        "Content-Type": "application/json",
        "Accept-Language": "ar",
    }

    json_data = {
        "channel": {"name": "MobileApp"},
        "orderItem": [
            {
                "action": "add",
                "product": {
                    "characteristic": [
                        {"name": "LangId", "value": "ar"},
                        {"name": "ExecutionType", "value": "Sync"},
                        {"name": "DropAddons", "value": "False"},
                        {"name": "OneStepMigrationFlag", "value": "Y"},
                        {"name": "Journey", "value": "MI_ELigibility"},
                    ],
                    "encProductId": package["encProductId"],
                    "id": package["id"],
                    "relatedParty": [{"id": phone, "name": "MSISDN", "role": "Subscriber"}],
                    "@type": "MI",
                },
                "eCode": 0,
            }
        ],
        "@type": "MIProfile",
    }

    try:
        response = requests.post(ORDER_URL, headers=headers, json=json_data, timeout=30)
        if response.status_code in [200, 201, 202]:
            return {
                "success": True,
                "message": f"تم تفعيل {package['name']} بنجاح",
                "price": package["price"],
                "quota": package["quota"],
                "duration": package["duration"],
            }
        return {"success": False, "message": f"فشل التفعيل: {response.status_code}"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


def choose_package(packages):
    """عرض الباقات على المستخدم وطلب الاختيار"""
    print("\n📦 باقات Plus المتاحة:\n")
    for pkg in packages:
        print(f"  {pkg['index']}. {pkg['name']} - {pkg['price']} جنيه "
              f"(الكمية: {pkg['quota']} | المدة: {pkg['duration']})")

    while True:
        choice = input("\n👉 اختر رقم الباقة (أو q للخروج): ").strip()
        if choice.lower() == "q":
            return None
        for pkg in packages:
            if str(pkg["index"]) == choice:
                return pkg
        print("❌ اختيار غير صحيح، حاول تاني")


def main():
    parser = argparse.ArgumentParser(description="اشتراك في باقات Plus - فودافون مصر")
    parser.add_argument("--phone", help="رقم الهاتف (مثال: 01xxxxxxxxx)")
    parser.add_argument("--password", help="كلمة مرور حساب انا فودافون")
    args = parser.parse_args()

    phone = args.phone or input("📱 أدخل رقم الهاتف: ").strip()
    password = args.password or getpass.getpass("🔑 أدخل كلمة المرور: ")

    print("\n⏳ جاري تسجيل الدخول...")
    auth_result = plus_login(phone, password)
    if not auth_result["success"]:
        print(f"❌ {auth_result['message']}")
        sys.exit(1)

    token = auth_result["token"]

    print("⏳ جاري جلب باقات Plus...")
    data = get_plus_packages(token, phone)
    if not data:
        print("❌ فشل جلب الباقات، تأكد من اتصالك أو أعد المحاولة")
        sys.exit(1)

    packages = parse_plus_packages(data)
    if not packages:
        print("❌ لا توجد باقات Plus متاحة على هذا الرقم حالياً")
        sys.exit(1)

    selected = choose_package(packages)
    if not selected:
        print("تم الإلغاء.")
        sys.exit(0)

    print(f"\n⏳ جاري تفعيل: {selected['name']} ...")
    result = activate_plus_package(token, phone, selected)

    if result["success"]:
        print(f"\n✅ {result['message']}")
        print(f"   💰 السعر: {result['price']} جنيه")
        print(f"   📶 الكمية: {result['quota']}")
        print(f"   ⏱️ المدة: {result['duration']}")
    else:
        print(f"\n❌ {result['message']}")


if __name__ == "__main__":
    main()
