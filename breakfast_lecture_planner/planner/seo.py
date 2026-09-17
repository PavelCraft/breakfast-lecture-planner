from xml.etree.ElementTree import Element, SubElement, tostring

from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from django.utils.translation import get_language


# Only the homepage and pages shown in the guest navigation belong in the sitemap.
PUBLIC_PAGES = {
    "planner:new": {
        "lt": ("Šri Šri Nitai Gaurasundaros šventykla | Malone.guru", "Šri Šri Nitai Gaurasundaros šventykla: dienos programa, vaišnavų kalendorius, šventyklos naujienos ir registracija šeštadienio pietums."),
        "en": ("Sri Sri Nitai Gaurasundara Temple | Malone.guru", "Explore the Sri Sri Nitai Gaurasundara Temple: daily schedule, Vaishnava calendar, temple news and registration for Saturday lunch."),
    },
    "planner:vaishnava_calendar": {
        "lt": ("Vaišnavų kalendorius | Malone.guru", "Vaišnavų kalendorius: ekadašio dienos, šventės ir kitos svarbios datos Šri Šri Nitai Gaurasundaros šventykloje."),
        "en": ("Vaishnava Calendar | Malone.guru", "Explore the Vaishnava calendar, including Ekadashi days, festivals and other important dates at the Sri Sri Nitai Gaurasundara Temple."),
    },
    "planner:renovation_work": {
        "lt": ("Šventyklos remonto darbai | Malone.guru", "Informacija apie Šri Šri Nitai Gaurasundaros šventyklos remonto darbus ir galimybes prisidėti prie šventyklos atnaujinimo."),
        "en": ("Temple Renovation | Malone.guru", "Information about renovation work at the Sri Sri Nitai Gaurasundara Temple and how to support the temple's renewal."),
    },
    "planner:principai": {
        "lt": ("Mūsų vertybės ir principai | Malone.guru", "Susipažinkite su Šri Šri Nitai Gaurasundaros šventyklos vertybėmis, principais ir vaišnavų bendruomenės gyvenimu."),
        "en": ("Our Values and Principles | Malone.guru", "Learn about the values and principles of the Sri Sri Nitai Gaurasundara Temple and its Vaishnava community."),
    },
    "planner:nuorodos": {
        "lt": ("Naudingos nuorodos | Malone.guru", "Naudingos nuorodos ir informacijos šaltiniai apie Šri Šri Nitai Gaurasundaros šventyklą bei vaišnavų tradiciją."),
        "en": ("Useful Links | Malone.guru", "Useful links and resources about the Sri Sri Nitai Gaurasundara Temple and the Vaishnava tradition."),
    },
}


def seo_context(request):
    match = getattr(request, "resolver_match", None)
    page = PUBLIC_PAGES.get(match.view_name) if match else None
    if not page:
        return {"seo_public": False}
    language = "lt" if get_language() == "lt" else "en"
    title, description = page[language]
    return {
        "seo_public": True,
        "seo_title": title,
        "seo_description": description,
        "seo_canonical": f"{settings.SEO_SITE_URL}{reverse(match.view_name)}",
    }


def sitemap(request):
    root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for view_name in PUBLIC_PAGES:
        url = SubElement(root, "url")
        SubElement(url, "loc").text = f"{settings.SEO_SITE_URL}{reverse(view_name)}"
    return HttpResponse(tostring(root, encoding="utf-8", xml_declaration=True), content_type="application/xml")


def robots_txt(request):
    content = f"User-agent: *\nAllow: /\nSitemap: {settings.SEO_SITE_URL}/sitemap.xml\n"
    return HttpResponse(content, content_type="text/plain; charset=utf-8")
