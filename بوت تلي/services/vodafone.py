import httpx
from typing import Any

CLIENT_SECRET = "95fd95fb-7489-4958-8ae6-d31a525cd20a"
CLIENT_ID = "ana-vodafone-app"
TOKEN_URL = "https://mobile.vodafone.com.eg/auth/realms/vf-realm/protocol/openid-connect/token"
OFFERING_URL = "https://mobile.vodafone.com.eg/services/dxl/epo/eligibleProductOffering"
ORDER_URL = "https://mobile.vodafone.com.eg/services/dxl/pom/productOrder"

class IntegrationUnavailable(RuntimeError):
    """Raised when an authorized Vodafone integration is not configured."""

class VodafonePlusService:
    @property
    def available(self) -> bool:
        return True

    async def login(self, phone: str, password: str) -> dict[str, Any]:
        """تسجيل الدخول والحصول على access token"""
        data = {
            "grant_type": "password",
            "username": phone,
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
            "msisdn": phone,
            "Accept-Language": "ar",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(TOKEN_URL, data=data, headers=headers)
                if response.status_code == 200:
                    token_data = response.json()
                    return {"success": True, "token": token_data.get("access_token")}
                return {"success": False, "message": f"الرقم أو كلمة المرور غير صحيحة (كود: {response.status_code})\nالتفاصيل: {response.text}"}
            except Exception as e:
                return {"success": False, "message": f"خطأ في الاتصال: {str(e)}"}

    async def get_packages(self, token: str, phone: str) -> list[dict[str, Any]]:
        """جلب كل عروض Plus المتاحة على الرقم"""
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(OFFERING_URL, params=params, headers=headers)
                if response.status_code == 200:
                    return self._parse_plus_packages(response.json())
                return []
            except Exception:
                return []

    def _parse_plus_packages(self, data: Any) -> list[dict[str, Any]]:
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

    async def activate_package(self, token: str, phone: str, package: dict[str, Any]) -> dict[str, Any]:
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
                        "encProductId": package.get("encProductId"),
                        "id": package.get("id"),
                        "relatedParty": [{"id": phone, "name": "MSISDN", "role": "Subscriber"}],
                        "@type": "MI",
                    },
                    "eCode": 0,
                }
            ],
            "@type": "MIProfile",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(ORDER_URL, headers=headers, json=json_data)
                if response.status_code in [200, 201, 202]:
                    return {
                        "success": True,
                        "message": f"تم تفعيل {package['name']} بنجاح",
                        "price": package["price"],
                        "quota": package["quota"],
                        "duration": package["duration"],
                    }
                return {"success": False, "message": f"فشل التفعيل (كود {response.status_code})"}
            except Exception as e:
                return {"success": False, "message": f"خطأ في الاتصال: {str(e)}"}
