from flask import request, current_app, url_for, g
from flask_babel import gettext as _
import json
from urllib.parse import urlencode


class SEOManager:
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.context_processor(self.context_processor)

    def context_processor(self):
        return dict(seo=self)

    @property
    def title(self):
        return g.get('seo_title', _('عصابات فلسطين'))

    @title.setter
    def title(self, value):
        g.seo_title = value

    @property
    def description(self):
        default_description = _(
            'عصابات فلسطين - اللعبة العربية الاستراتيجية الأولى. عش تجربة حياة الجريمة المنظمة، '
            'ابنِ إمبراطوريتك في القدس وغزة، وتحدى الاحتلال. نافس آلاف اللاعبين في حروب العصابات. '
            'سجل الآن مجاناً!')
        return g.get('seo_description', default_description)

    @description.setter
    def description(self, value):
        g.seo_description = value

    @property
    def keywords(self):
        # Enhanced keywords for better visibility on Google and YouTube
        default_keywords = _(
            "عصابات فلسطين, Gangs of Palestine, لعبة مافيا, حرب العصابات, العاب استراتيجية, فلسطين, "
            "القدس, غزة, العاب عربية, Mafia Game, Online RPG, Browser Game, العاب اونلاين, العاب اكشن, "
            "لعبة حرب, العاب متصفح, العاب مجانية, Free Games, Strategy Games, Multiplayer, PvP, Clan Wars, "
            "Palestine Game, Gaza, Jerusalem, Azad Company, العاب يوتيوب, العاب مشهورة"
        )
        return g.get('seo_keywords', default_keywords)

    @keywords.setter
    def keywords(self, value):
        g.seo_keywords = value

    @property
    def image(self):
        default_image = url_for(
            'static',
            filename='images/azad_logo_white_on_dark.png',
            _external=True)
        return g.get('seo_image', default_image)

    @image.setter
    def image(self, value):
        if not value.startswith('http'):
            # Assume it's a static file path if not a full URL
            # But usually we pass full URL or handle it here.
            # For safety, let's assume the caller passes a full URL or we use url_for if needed.
            # Here we just store what is passed.
            pass
        g.seo_image = value

    @property
    def url(self):
        return request.url

    @property
    def type(self):
        return g.get('seo_type', 'website')

    @type.setter
    def type(self, value):
        g.seo_type = value

    @property
    def schema(self):
        return g.get('seo_schema', None)

    @schema.setter
    def schema(self, value):
        """
        Set structured data (JSON-LD dictionary).
        """
        g.seo_schema = value

    @property
    def robots(self):
        default_robots = "index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"
        return g.get('seo_robots', default_robots)

    @robots.setter
    def robots(self, value):
        g.seo_robots = value

    def set(
            self,
            title=None,
            description=None,
            keywords=None,
            image=None,
            type=None,
            schema=None,
            robots=None):
        """
        Helper to set multiple properties at once.
        """
        if title:
            self.title = title
        if description:
            self.description = description
        if keywords:
            self.keywords = keywords
        if image:
            self.image = image
        if type:
            self.type = type
        if schema:
            self.schema = schema
        if robots:
            self.robots = robots

    @property
    def breadcrumbs(self):
        return g.get('seo_breadcrumbs', [])

    def add_breadcrumb(self, name, url):
        if url and isinstance(url, str) and url.startswith("/"):
            try:
                url = request.url_root.rstrip("/") + url
            except Exception:
                pass
        breadcrumbs = self.breadcrumbs
        # Check if already exists to avoid duplicates if called multiple times
        if not any(b['item'] == url for b in breadcrumbs):
            breadcrumbs.append({'name': name, 'item': url})
        g.seo_breadcrumbs = breadcrumbs

    def render_breadcrumbs_schema(self):
        breadcrumbs = self.breadcrumbs
        if not breadcrumbs:
            return ""

        items = []
        for i, crumb in enumerate(breadcrumbs):
            # Fix for Google Search Console: Use simple ID reference
            items.append({
                "@type": "ListItem",
                "position": i + 1,
                "name": crumb['name'],
                "item": crumb['item']
            })

        schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": items
        }

        return (
            '<script type="application/ld+json">'
            + json.dumps(schema)
            + "</script>"
        )

    def render_canonical(self):
        ignored_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "gclid",
            "fbclid",
            "ref",
            "next",
        }
        args = request.args.to_dict(flat=False)
        for k in list(args.keys()):
            if k in ignored_params:
                args.pop(k, None)

        lang = request.args.get('lang')
        if lang in current_app.config.get('LANGUAGES', ['ar', 'en']):
            args["lang"] = [lang]
        else:
            args.pop("lang", None)

        qs = urlencode(args, doseq=True)
        href = request.base_url + (f"?{qs}" if qs else "")
        return f'<link rel="canonical" href="{href}">'

    def render_hreflang(self):
        langs = current_app.config.get('LANGUAGES', ['ar', 'en'])
        ignored_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "gclid",
            "fbclid",
            "ref",
            "next",
        }
        base_args = request.args.to_dict(flat=False)
        for k in list(base_args.keys()):
            if k in ignored_params:
                base_args.pop(k, None)

        args_no_lang = dict(base_args)
        args_no_lang.pop("lang", None)
        qs_default = urlencode(args_no_lang, doseq=True)
        href_default = request.base_url + \
            (f"?{qs_default}" if qs_default else "")

        tags = [
            f'<link rel="alternate" hreflang="x-default" href="{href_default}">']
        for lang_code in langs:
            args = dict(base_args)
            args["lang"] = [lang_code]
            qs = urlencode(args, doseq=True)
            href = request.base_url + (f"?{qs}" if qs else "")
            tags.append(
                f'<link rel="alternate" hreflang="{lang_code}" href="{href}">')
        return "".join(tags)
