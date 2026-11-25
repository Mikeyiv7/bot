import argparse
import base64
import getpass
import sys
import requests

LOGIN_URL = "https://mab.etisalat.com.eg:11003/Saytar/rest/authentication/loginWithPlan"
ORDER_URL = "https://mab.etisalat.com.eg:11003/Saytar/rest/servicemanagement/submitOrderV2"

GIFTS = {
    "social": {"name": "500 ميجا سوشيال", "product": "DOWNLOAD_GIFT_1_SOCIAL_UNITS"},
    "streaming": {"name": "500 ميجا ستريمنج", "product": "DOWNLOAD_GIFT_2_STREAMING_UNITS"},
}


def activate_etisalat_gift(number: str, password: str, email: str, gift_type: str = "all") -> dict:
    """تفعيل هدايا اتصالات (سوشيال / ستريمنج / الكل)"""
    clean_phone = number.strip()
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

    try:
        log_res = requests.post(LOGIN_URL, headers=headerslog, data=datalog, timeout=30)
        if "true" not in log_res.text.lower():
            return {"success": False, "message": "❌ الرقم أو كلمة السر أو الإيميل غير صحيح."}

        st = log_res.headers.get("Set-Cookie", "")
        ck = st.split(";")[0] if st else ""
        br = log_res.headers.get("auth", "")

        if gift_type == "social":
            products_to_redeem = [GIFTS["social"]]
        elif gift_type == "streaming":
            products_to_redeem = [GIFTS["streaming"]]
        else:
            products_to_redeem = [GIFTS["social"], GIFTS["streaming"]]

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

        results = []
        for item in products_to_redeem:
            datasub = (
                "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"
                "<submitOrderRequest><mabOperation></mabOperation>"
                f"<msisdn>{num}</msisdn><operation>REDEEM</operation>"
                f"<productName>{item['product']}</productName></submitOrderRequest>"
            )
            sub_res = requests.post(ORDER_URL, headers=headerssub, data=datasub, timeout=30)
            if "true" in sub_res.text.lower():
                results.append(f"✅ {item['name']}: تم التفعيل بنجاح")
            else:
                results.append(f"⚠️ {item['name']}: البيانات غير صحيحة أو العرض متفعل بالفعل")

        return {"success": any("✅" in r for r in results), "message": "\n".join(results)}
    except Exception as e:
        return {"success": False, "message": f"❌ خطأ في الاتصال: {str(e)}"}


def activate_etisalat_social_gift(number: str, password: str, email: str) -> dict:
    return activate_etisalat_gift(number, password, email, gift_type="social")


def activate_etisalat_streaming_gift(number: str, password: str, email: str) -> dict:
    return activate_etisalat_gift(number, password, email, gift_type="streaming")


def main():
    parser = argparse.ArgumentParser(description="تفعيل هدايا اتصالات (سوشيال / ستريمنج / الكل)")
    parser.add_argument("--phone", help="رقم الهاتف (مثال: 011xxxxxxxx)")
    parser.add_argument("--password", help="كلمة المرور")
    parser.add_argument("--email", help="البريد الإلكتروني")
    parser.add_argument("--type", choices=["social", "streaming", "all"], default="all", help="نوع الهدايا")
    args = parser.parse_args()

    phone = args.phone or input("📱 أدخل رقم اتصالات: ").strip()
    password = args.password or getpass.getpass("🔑 أدخل كلمة السر: ").strip()
    email = args.email or input("📧 أدخل الإيميل: ").strip()

    print("\n⏳ جاري طلب التفعيل...")
    res = activate_etisalat_gift(phone, password, email, gift_type=args.type)
    print(res["message"])


if __name__ == "__main__":
    main()
