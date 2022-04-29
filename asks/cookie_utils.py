__all__ = ["CookieTracker", "parse_cookies"]


from typing import Any, Optional, Union

from .response_objects import BaseResponse, Cookie

_CookiesToSend = dict[Optional[str], Optional[str]]


class CookieTracker:
    """
    Class for holding cookies in sessions, adding statefullness to
    the otherwise stateless general http method functions.
    """

    def __init__(self) -> None:
        self.domain_dict: dict[str, list[Cookie]] = {}

    def get_additional_cookies(self, netloc: str, path: str) -> _CookiesToSend:
        netloc = netloc.replace("://www.", "://", 1)
        return self._check_cookies(netloc + path)

    def _store_cookies(self, response_obj: BaseResponse[Any]) -> None:
        for cookie in response_obj.cookies:
            try:
                self.domain_dict[cookie.host.lstrip()].append(cookie)
            except KeyError:
                self.domain_dict[cookie.host.lstrip()] = [cookie]

    def _check_cookies(self, endpoint: str) -> _CookiesToSend:
        relevant_domains = []
        domains = self.domain_dict.keys()

        if domains:
            paths = []
            for path in endpoint.split("/"):
                paths.append(path)
                check_domain = "/".join(paths)
                if check_domain in domains:
                    relevant_domains.append(check_domain)
        return self._get_cookies_to_send(relevant_domains)

    def _get_cookies_to_send(self, domain_list: list[str]) -> _CookiesToSend:
        cookies_to_go: dict[Optional[str], Optional[str]] = {}
        for domain in domain_list:
            for cookie_obj in self.domain_dict[domain]:
                cookies_to_go[cookie_obj.name] = cookie_obj.value
        return cookies_to_go


def parse_cookies(response: BaseResponse[Any], host: str) -> None:
    """
    Sticks cookies to a response.
    """
    cookie_pie = []
    try:
        for cookie in response.headers["set-cookie"]:
            cookie_jar: dict[str, Union[str, bool]] = {}
            name_val, *rest = cookie.split(";")
            name, value = name_val.split("=", 1)
            cookie_jar["name"] = name.strip()
            cookie_jar["value"] = value
            for item in rest:
                try:
                    name, value = item.split("=")
                    if value.startswith("."):
                        value = value[1:]
                    cookie_jar[name.lower().lstrip()] = value
                except ValueError:
                    cookie_jar[item.lower().lstrip()] = True
            cookie_pie.append(cookie_jar)
        response.cookies = [Cookie(host, x) for x in cookie_pie]
    except KeyError:
        pass
