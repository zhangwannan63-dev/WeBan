import unittest
from unittest.mock import Mock, patch
import requests
from api import LoggingSession

class RetryTests(unittest.TestCase):
    def session(self, effects):
        client = LoggingSession(log=Mock())
        client._session = Mock()
        client._session.request.side_effect = effects
        return client

    def test_resource_recovers_with_backoff(self):
        response = Mock(status_code=200)
        client = self.session([requests.ConnectTimeout(), requests.ReadTimeout(), response])
        with patch("api.time.sleep") as sleep:
            self.assertIs(client.get("https://jxstatic.mycourse.cn/WEIBAN/resource/a.m3u8", timeout=10), response)
        self.assertEqual([x.args[0] for x in sleep.call_args_list], [3, 6])
        self.assertEqual(client._session.request.call_args.kwargs["timeout"], (30, 60))

    def test_resource_retry_is_bounded(self):
        client = self.session([requests.ConnectTimeout()] * 4)
        with patch("api.time.sleep"), self.assertRaises(requests.ConnectTimeout):
            client.get("https://mcwk.mycourse.cn/course/a/a.html")
        self.assertEqual(client._session.request.call_count, 4)

    def test_api_writes_and_finish_get_never_replay(self):
        for method, url in [("POST", "https://safety.mycourse.cn/brainprovider/router"),
                            ("POST", "https://weiban.mycourse.cn/exam/submit.do"),
                            ("GET", "https://weiban.mycourse.cn/pharos/usercourse/v2/x.do"),
                            ("POST", "https://mcwk.mycourse.cn/course/x")]:
            client = self.session([requests.ReadTimeout()])
            with self.assertRaises(requests.ReadTimeout):
                client.request(method, url)
            self.assertEqual(client._session.request.call_count, 1)

    def test_temporary_status_retry_but_no_security_retry(self):
        for status, count in [(503, 2), (403, 1), (701, 1), (429, 1)]:
            first = Mock(status_code=status)
            client = self.session([first, Mock(status_code=200)])
            with patch("api.time.sleep"):
                client.get("https://mcwk.mycourse.cn/course/a.js")
            self.assertEqual(client._session.request.call_count, count)

if __name__ == "__main__":
    unittest.main()
