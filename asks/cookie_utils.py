__all__ = ['CookieTracker']


class CookieTracker:
    '''
    Class for holding cookies in sessions, adding statefullness to
    the otherwise stateless general http method functions.
    '''
    def __init__(self):
        self.domain_dict = {}

    def get_additional_cookies(self, netloc, path):
        netloc = netloc.replace('://www.', '://', 1)
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
            paths = []
            for path in endpoint.split('/'):
                paths.append(path)
                check_domain = '/'.join(paths)
                if check_domain in domains:
                    relevant_domains.append(check_domain)
        return self._get_cookies_to_send(relevant_domains)

    def _get_cookies_to_send(self, domain_list):
        cookies_to_go = {}
        for domain in domain_list:
            for cookie_obj in self.domain_dict[domain]:
                cookies_to_go[cookie_obj.name] = cookie_obj.value
        return cookies_to_go
