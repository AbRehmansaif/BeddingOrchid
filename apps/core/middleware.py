import time

class TrackingMiddleware:
    """
    Captures marketing attribution parameters (UTM, Meta fbclid, Google gclid, _fbp)
    from request cookies and query parameters, and stores them in the session.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not hasattr(request, 'session'):
            return self.get_response(request)

        attribution = request.session.get('marketing_attribution', {})

        # 1. Capture UTM parameters
        utm_keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']
        has_new_utm = False
        for key in utm_keys:
            val = request.GET.get(key)
            if val:
                attribution[key] = val
                has_new_utm = True

        # 2. Capture Click IDs
        fbclid = request.GET.get('fbclid')
        if fbclid:
            attribution['fbclid'] = fbclid
            # Build standard fbc: fb.1.subdomainIndex.creationTimestamp.fbclid
            timestamp = int(time.time() * 1000)
            attribution['fbc'] = f"fb.1.{timestamp}.{fbclid}"

        gclid = request.GET.get('gclid')
        if gclid:
            attribution['gclid'] = gclid

        # 3. Capture Facebook Browser ID (_fbp cookie)
        fbp = request.COOKIES.get('_fbp')
        if fbp:
            attribution['fbp'] = fbp

        # 4. Capture Landing Page & Referrer (first touch if not set)
        if 'landing_page' not in attribution and not request.path.startswith('/static/') and not request.path.startswith('/media/'):
            attribution['landing_page'] = request.build_absolute_uri()
            attribution['referrer'] = request.META.get('HTTP_REFERER', '')

        # Always update last touch
        if has_new_utm or fbclid or gclid:
            attribution['last_touch_url'] = request.build_absolute_uri()

        request.session['marketing_attribution'] = attribution
        request.marketing_attribution = attribution

        response = self.get_response(request)
        return response
