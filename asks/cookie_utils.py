'''
Class for holding cookies in sessions, adding statefullness to
the otherwise stateless general http method functions.
'''


__all__ = ['CookieTracker']


class CookieTracker:

    def __init__(self):
        self.domain_dict = {}

    def get_additional_cookies(self, netloc, path):
        netloc = netloc.replace('www.', '')
        return self._check_cookies(netloc + path)

    def _store_cookies(self, response_obj):
        for cookie in response_obj.cookies:
            try:
                self.domain_dict[cookie.host.lstrip()].append(cookie)
            except KeyError:
                self.domain_dict[cookie.host.lstrip()] = [cookie]

    def _check_cookies(self, endpoint):
        relevant_domains = []
        domains = self.domain_dict.keys()

        if domains:
            if endpoint in domains:
                relevant_domains.append(self.domain_dict[endpoint])
            parts = endpoint.split('/')

            for index in range(1, len(parts)):
                check_domain = '/'.join(parts[:-index])
                if check_domain in domains:
                    relevant_domains.append(self.domain_dict[check_domain])
        return self._get_cookies_to_send(relevant_domains)

    def _get_cookies_to_send(self, domain_list):
        cookies_to_go = {}
        for domain in domain_list:
            for cookie_obj in domain:
                cookies_to_go[cookie_obj.name] = cookie_obj.value
        return cookies_to_go
