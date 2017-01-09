import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Union, Dict

Json = Union[list, dict]


class Requester(object):
    def request_json(self, url: str, headers: Dict[str, str] = None, data: bytes = None) -> Json:
        headers = headers or {}
        content = self.request(url, headers, data, "application/json")
        doc = json.loads(content)
        return doc

    @staticmethod
    def request(url: str, headers: Dict[str, str] = None, data: bytes = None, expected_content_type: str = None) -> str:
        headers = headers or {}
        method = "POST" if data else "GET"
        req = urllib.request.Request(url, headers=headers, method=method, data=data)
        try:
            with urllib.request.urlopen(req) as res:
                if res.getcode == 204:
                    raise NoContentException(204, res.geturl())
                if expected_content_type:
                    if res.headers.get_content_type() != expected_content_type:
                        raise WrongContentTypeException(res.headers.get_content_type())
                return res.read().decode(res.headers.get_content_charset())
        except (urllib.error.HTTPError, NoContentException, WrongContentTypeException) as e:
            raise RequesterException("Error during request to {}".format(url)) from e


class ExceptionWithReason(Exception):
    def __init__(self, message: str = None) -> None:
        if message:
            self._message = message
        else:
            self._message = self.__class__.__name__

    @property
    def message(self) -> str:
        if self.__cause__:
            if isinstance(self.__cause__, ExceptionWithReason):
                return "{}: {}".format(self._message, self.__cause__.message)
            else:
                return "{}: {}".format(self._message, str(self.__cause__))
        else:
            return self._message

    def __str__(self) -> str:
        return self.message


class RequesterException(ExceptionWithReason):
    def getcode(self) -> int:
        return self.__cause__.getcode() if hasattr(self.__cause__, "getcode") else None

    def geturl(self) -> str:
        return self.__cause__.geturl() if hasattr(self.__cause__, "geturl") else None


class NoContentException(ExceptionWithReason):
    def __init__(self, code: int, url: str) -> None:
        self.code = code
        self.url = url

    def getcode(self) -> int:
        return self.code

    def geturl(self) -> str:
        return self.url


class WrongContentTypeException(ExceptionWithReason):
    def __init__(self, content_type: str) -> None:
        super().__init__("Received unexpected content type '{}'".format(content_type))


class Client(object):
    def __init__(self, requester: Requester, api_url: str, headers: Dict[str, str] = None) -> None:
        self.requester = requester
        self.api_url = api_url
        self.headers = headers or {}

    def add_header(self, key: str, value: str) -> None:
        self.headers[key] = value

    def request_raw(self, path: str, data: bytes = None) -> str:
        try:
            return self.requester.request(self.api_url + path, self.headers, data)
        except RequesterException as e:
            raise ClientException("Client error") from e

    def request_json(self, path: str, data: bytes = None) -> Json:
        try:
            return self.requester.request_json(self.api_url + path, self.headers, data)
        except RequesterException as e:
            raise ClientException("Client error") from e


class ClientException(ExceptionWithReason):
    def getcode(self) -> int:
        return self.__cause__.getcode() if self.__cause__ else None

    def geturl(self) -> str:
        return self.__cause__.geturl() if self.__cause__ else None
