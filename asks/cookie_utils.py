'''
Class for holding cookies in sessions, adding statefullness to
the otherwise stateless general http method functions.
'''


__all__ = ['CookieTracker']


class CookieTracker:

    def __init__(self):
        self.current_epoint = None
        self.domain_dict = {}

    def get_current_endpoint(self, netloc, path):
            netloc = netloc.replace('www.', '')
            self.current_epoint = netloc + path

    def _store_cookies(self, response_obj):
        for cookie in response_obj.cookies:
            try:
                self.domain_dict[cookie.host.lstrip()].append(cookie)
            except KeyError:
                self.domain_dict[cookie.host.lstrip()] = [cookie]

    def _check_cookies(self):
        relevant_domains = []
        domains = self.domain_dict.keys()

        if domains:
            if self.current_epoint in domains:
                relevant_domains.append(self.domain_dict[self.current_epoint])
            parts = self.current_epoint.split('/')

            for index, path_chunk in enumerate(parts, start=1):
                check_domain = '/'.join(parts[:index*-1])
                if check_domain in domains:
                    relevant_domains.append(self.domain_dict[check_domain])
        return self._get_cookies_to_send(relevant_domains)

    def _get_cookies_to_send(self, domain_list):
        cookies_to_go = {}
        for domain in domain_list:
            for cookie_obj in domain:
                cookies_to_go[cookie_obj.name] = cookie_obj.value
        return cookies_to_go
