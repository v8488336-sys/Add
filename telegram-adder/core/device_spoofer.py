import random

ANDROID_DEVICES = [
    ("Samsung Galaxy S23", "Android 13"),
    ("Samsung Galaxy S22 Ultra", "Android 12"),
    ("Samsung Galaxy A54", "Android 13"),
    ("Samsung Galaxy S21", "Android 12"),
    ("Xiaomi 13 Pro", "Android 13"),
    ("Xiaomi Redmi Note 12", "Android 12"),
    ("OnePlus 11", "Android 13"),
    ("OnePlus 10 Pro", "Android 12"),
    ("Google Pixel 7 Pro", "Android 13"),
    ("Google Pixel 6a", "Android 13"),
    ("Oppo Find X6", "Android 13"),
    ("Realme GT 3", "Android 13"),
    ("Vivo X90 Pro", "Android 13"),
    ("Huawei P60 Pro", "Android 12"),
    ("Sony Xperia 1 V", "Android 13"),
]

IOS_DEVICES = [
    ("iPhone 14 Pro Max", "iOS 16.5"),
    ("iPhone 14 Pro", "iOS 16.4"),
    ("iPhone 14", "iOS 16.3"),
    ("iPhone 13 Pro Max", "iOS 16.2"),
    ("iPhone 13 Pro", "iOS 15.7"),
    ("iPhone 13", "iOS 16.1"),
    ("iPhone 12 Pro", "iOS 15.6"),
    ("iPhone 12", "iOS 15.5"),
]

DESKTOP_DEVICES = [
    ("Desktop", "Windows 11"),
    ("Desktop", "Windows 10"),
    ("MacBook Pro", "macOS 13.4"),
    ("MacBook Air", "macOS 13.3"),
    ("Desktop", "Ubuntu 22.04"),
]

TG_APP_VERSIONS = [
    "9.6.3", "9.7.1", "9.8.0", "10.0.1", "10.1.0",
    "10.2.0", "10.3.0", "10.4.1", "10.5.0", "10.6.0",
]

LANG_CODES = ["en", "ar", "ru", "de", "fr", "tr", "es", "pt", "it", "nl"]


def generate_device_params():
    device_type = random.choices(["android", "ios", "desktop"], weights=[60, 30, 10])[0]

    if device_type == "android":
        device_model, system_version = random.choice(ANDROID_DEVICES)
        app_version = random.choice(TG_APP_VERSIONS)
        lang_code = random.choice(LANG_CODES)
        lang_pack = ""
        system_lang_code = lang_code
    elif device_type == "ios":
        device_model, system_version = random.choice(IOS_DEVICES)
        app_version = random.choice(TG_APP_VERSIONS)
        lang_code = random.choice(LANG_CODES)
        lang_pack = ""
        system_lang_code = lang_code
    else:
        device_model, system_version = random.choice(DESKTOP_DEVICES)
        app_version = random.choice(TG_APP_VERSIONS)
        lang_code = random.choice(LANG_CODES)
        lang_pack = ""
        system_lang_code = lang_code

    return {
        "device_model": device_model,
        "system_version": system_version,
        "app_version": app_version,
        "lang_code": lang_code,
        "lang_pack": lang_pack,
        "system_lang_code": system_lang_code,
    }


def get_random_name():
    first_names = [
        "Ahmed", "Mohamed", "Ali", "Omar", "Hassan", "Khalid", "Yusuf",
        "Ibrahim", "Samir", "Tariq", "Nour", "Layla", "Fatima", "Amira",
        "Sara", "Dina", "Rania", "Hana", "Mona", "Rana",
        "James", "John", "Michael", "David", "Robert", "William",
        "Emma", "Olivia", "Ava", "Isabella", "Sophia", "Charlotte",
    ]
    last_names = [
        "Al-Ahmad", "Al-Hassan", "Ibrahim", "Khalil", "Mansour",
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Davis",
        "Mueller", "Schmidt", "Fischer", "Weber", "Wagner",
    ]
    return random.choice(first_names), random.choice(last_names)


def get_random_bio():
    bios = [
        "Living life one day at a time",
        "Entrepreneur | Traveler | Dreamer",
        "Coffee lover ☕",
        "Tech enthusiast",
        "Just here to connect",
        "🌍 World explorer",
        "Business & Lifestyle",
        "Photographer | Writer",
        "",
        "",
        "",
    ]
    return random.choice(bios)
