import base64
import httpx
from typing import Any

LOGIN_URL = "https://mab.etisalat.com.eg:11003/Saytar/rest/authentication/loginWithPlan"
ORDER_URL = "https://mab.etisalat.com.eg:11003/Saytar/rest/servicemanagement/submitOrderV2"

GIFTS = {
    "social": {
        "name": "500 ميجا سوشيال",
        "product": "DOWNLOAD_GIFT_1_SOCIAL_UNITS",
    },
    "streaming": {
        "name": "500 ميجا ستريمنج",
        "product": "DOWNLOAD_GIFT_2_STREAMING_UNITS",
    },
}


class EtisalatService:
    async def activate_gift(
        self, phone: str, password: str, email: str, gift_type: str = "all"
    ) -> dict[str, Any]:
        """تفعيل هدايا اتصالات (سوشيال / ستريمنج / الكل)"""
        clean_phone = phone.strip()
        if clean_phone.startswith("011"):
            num = clean_phone[1:]
        elif clean_phone.startswith("+2011"):
            num = clean_phone[3:]
        elif clean_phone.startswith("2011"):
            num = clean_phone[2:]
        else:
            num = clean_phone

        code = f"{email.strip()}:{password.strip()}"
        auth = base64.b64encode(code.encode("ascii")).decode("ascii")
        xauth = f"Basic {auth}"

        headerslog = {
            "applicationVersion": "2",
            "applicationName": "MAB",
            "Accept": "text/xml",
            "Authorization": xauth,
            "APP-BuildNumber": "964",
            "APP-Version": "27.0.0",
            "OS-Type": "Android",
            "OS-Version": "12",
            "APP-STORE": "GOOGLE",
            "Is-Corporate": "false",
            "Content-Type": "text/xml; charset=UTF-8",
            "Host": "mab.etisalat.com.eg:11003",
            "Connection": "Keep-Alive",
            "User-Agent": "okhttp/5.0.0-alpha.11",
        }

        datalog = (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"
            "<loginRequest><deviceId></deviceId><firstLoginAttempt>true</firstLoginAttempt>"
            "<modelType></modelType><osVersion></osVersion><platform>Android</platform>"
            "<udid></udid></loginRequest>"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                log_res = await client.post(LOGIN_URL, headers=headerslog, content=datalog)
                log_text = log_res.text

                if "true" not in log_text.lower():
                    return {
                        "success": False,
                        "message": "❌ بيانات الدخول غير صحيحة (الرقم أو كلمة السر أو الإيميل).",
                    }

                cookie_header = log_res.headers.get("Set-Cookie", "")
                ck = cookie_header.split(";")[0] if cookie_header else ""
                br = log_res.headers.get("auth", "")

                if gift_type == "social":
                    products_to_redeem = [GIFTS["social"]]
                elif gift_type == "streaming":
                    products_to_redeem = [GIFTS["streaming"]]
                else:
                    products_to_redeem = [GIFTS["social"], GIFTS["streaming"]]

                results = []
                headerssub = {
                    "applicationVersion": "2",
                    "applicationName": "MAB",
                    "Accept": "text/xml",
                    "Cookie": ck,
                    "Language": "ar",
                    "APP-BuildNumber": "10501",
                    "APP-Version": "30.2.0",
                    "OS-Type": "Android",
                    "OS-Version": "7.1.2",
                    "APP-STORE": "GOOGLE",
                    "auth": f"Bearer {br}",
                    "Is-Corporate": "false",
                    "Content-Type": "text/xml; charset=UTF-8",
                    "Host": "mab.etisalat.com.eg:11003",
                    "Connection": "Keep-Alive",
                    "User-Agent": "okhttp/5.0.0-alpha.11",
                }

                for item in products_to_redeem:
                    datasub = (
                        "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"
                        "<submitOrderRequest><mabOperation></mabOperation>"
                        f"<msisdn>{num}</msisdn><operation>REDEEM</operation>"
                        f"<productName>{item['product']}</productName></submitOrderRequest>"
                    )
                    sub_res = await client.post(ORDER_URL, headers=headerssub, content=datasub)
                    if "true" in sub_res.text.lower():
                        results.append(f"✅ {item['name']}: تم التفعيل بنجاح")
                    else:
                        results.append(f"⚠️ {item['name']}: متفعل بالفعل أو غير متاح")

                success_any = any("✅" in r for r in results)
                msg = "\n".join(results)
                return {
                    "success": success_any,
                    "message": msg,
                    "quota": "1 GB (Social + Streaming)" if len(products_to_redeem) > 1 else products_to_redeem[0]["name"],
                    "price": 0.0,
                }
            except Exception as e:
                return {"success": False, "message": f"خطأ في الاتصال بالسيرفر: {str(e)}"}

    async def activate_social_gift(
        self, phone: str, password: str, email: str
    ) -> dict[str, Any]:
        return await self.activate_gift(phone, password, email, gift_type="social")

    async def activate_streaming_gift(
        self, phone: str, password: str, email: str
    ) -> dict[str, Any]:
        return await self.activate_gift(phone, password, email, gift_type="streaming")
