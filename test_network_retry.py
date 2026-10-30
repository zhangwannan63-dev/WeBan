import unittest
from unittest.mock import Mock, patch
import requests
from api import LoggingSession

class ReadingDurationTests(unittest.TestCase):
    def test_article_two_minute_guard(self):
        from client import _minimum_reading_seconds
        script = "const startTime = Date.now(); const timeDifference = currentTime - startTime; if (timeDifference >= 2 * 60 * 1000) { finishWxCourse(); }"
        self.assertEqual(_minimum_reading_seconds(script), 120)

    def test_plain_course_has_no_extra_guard(self):
        from client import _minimum_reading_seconds
        self.assertEqual(_minimum_reading_seconds("finishWxCourse();"), 0)

    def test_expression_is_not_executed(self):
        from client import _minimum_reading_seconds
        script = "startTime = Date.now(); timeDifference = currentTime - startTime; if (timeDifference >= alert(120000)) {}"
        self.assertEqual(_minimum_reading_seconds(script), 0)

class CompletionReconciliationTests(unittest.TestCase):
    def setUp(self):
        from client import WeBanClient, CourseCompletionError
        self.client = object.__new__(WeBanClient)
        self.client.api = Mock()
        self.client.log = Mock()
        self.course = {"resourceId": "target", "resourceName": "course", "finished": 2}
        self.task = {"userProjectId": "project"}
        self.client.get_progress = Mock(return_value={"code": "0", "data": {
            "requiredFinishedNum": 28, "pushFinishedNum": 0, "optionalFinishedNum": 0,
        }})
        self.client._study_one_course = Mock(side_effect=CourseCompletionError(
            "course", {"code": "-1", "detailCode": "-101"}
        ))

    def learn(self):
        return self.client._learn_course(
            self.course, self.task, "category", "project", {}, False,
            choose_type=3, category_code="category-code",
        )

    def test_exact_course_confirmed_without_replaying_study(self):
        self.client.api.list_course.return_value = {"code": "0", "data": [
            {"resourceId": "target", "finished": "1"},
        ]}
        self.assertTrue(self.learn())
        self.client._study_one_course.assert_called_once()
        self.client.api.list_course.assert_called_once_with("project", "category-code", 3)
        self.assertEqual([c[0] for c in self.client.api.mock_calls], ["list_course"])

    def test_delayed_finished_flag_only_retries_reads(self):
        self.client.api.list_course.side_effect = [
            {"code": "0", "data": [{"resourceId": "target", "finished": 2}]},
            {"code": "0", "data": [{"resourceId": "target", "finished": 1}]},
        ]
        with patch("client.time.sleep"):
            self.assertTrue(self.learn())
        self.assertEqual(self.client.api.list_course.call_count, 2)
        self.client._study_one_course.assert_called_once()

    def test_other_courses_and_higher_total_do_not_confirm_target(self):
        self.client.api.list_course.return_value = {"code": "0", "data": [
            {"resourceId": "other", "finished": 1},
            {"resourceId": "target", "finished": 2},
        ]}
        with patch("client.time.sleep"), self.assertRaisesRegex(RuntimeError, "平台未确认"):
            self.learn()
        self.client._study_one_course.assert_called_once()

    def test_missing_target_is_not_complete(self):
        self.client.api.list_course.return_value = {"code": "0", "data": []}
        with patch("client.time.sleep"), self.assertRaisesRegex(RuntimeError, "平台未确认"):
            self.learn()

    def test_security_error_during_verification_stops_immediately(self):
        self.client.api.list_course.side_effect = PermissionError("locked")
        with self.assertRaises(PermissionError):
            self.learn()
        self.client.api.list_course.assert_called_once()

    def test_unavailable_status_cannot_be_treated_as_success(self):
        self.client.api.list_course.side_effect = requests.ConnectTimeout()
        self.client.get_progress.side_effect = [{"code": "-1"}, requests.ConnectTimeout()]
        with patch("client.time.sleep"), self.assertRaisesRegex(RuntimeError, "平台未确认"):
            self.learn()
        self.assertEqual(self.client.api.list_course.call_count, 3)

    def test_other_business_errors_are_not_reconciled(self):
        from client import CourseCompletionError
        self.client._study_one_course.side_effect = CourseCompletionError(
            "course", {"code": "-1", "detailCode": "-999"}
        )
        with self.assertRaises(CourseCompletionError):
            self.learn()
        self.client.api.list_course.assert_not_called()

    def test_flat_course_verification_uses_project_and_type_on_all_pages(self):
        self.client.api.list_flat_course.side_effect = [
            {"code": "0", "data": {"totalPages": 2, "paginateData": [
                {"resourceId": "other", "finished": 1}]}},
            {"code": "0", "data": {"totalPages": 2, "paginateData": [
                {"resourceId": "target", "finished": 1}]}},
        ]
        self.assertTrue(self.client._course_finished_on_server(self.course, self.task, 2, None))
        self.assertEqual([c.args for c in self.client.api.list_flat_course.call_args_list], [
            ("project", 2, 1, 12), ("project", 2, 2, 12),
        ])

    def test_course_url_is_authoritative_and_ratings_are_optional(self):
        from client import WeBanClient
        self.client._build_course_url = Mock(return_value=(
            "https://mcwk.mycourse.cn/course/demo/demo.html?"
            "userCourseId=current&weiban=weiban&csComm=true"
        ))
        self.client.parse_item_js = Mock(return_value={"uses_apinext": False})
        self.client._finish_course = Mock(return_value={"code": "0"})
        self.client.api.study.return_value = {"code": "0"}
        self.client.study_base_time = self.client.study_random_upper = 0
        self.client.video_speed = 0
        self.client.jupiter_fallback = False
        self.course["userCourseId"] = "stale"
        self.assertTrue(WeBanClient._study_one_course(
            self.client, self.course, self.task, "category", "project", {}, False
        ))
        self.assertEqual(self.course["userCourseId"], "current")
        self.client._finish_course.assert_called_once()
        self.client.api.get_course_rating.assert_not_called()
        self.client.api.get_course_neighbors.assert_not_called()


class ExamSubmitThresholdTests(unittest.TestCase):
    def test_random_answers_never_bypass_minimum_match_rate(self):
        from client import WeBanClient
        for mode in ("true", "perfect", "force"):
            for random_answer in (True, False):
                with self.subTest(mode=mode, random_answer=random_answer):
                    client = object.__new__(WeBanClient)
                    client.log = Mock()
                    client.api = Mock()
                    client.ai_config = {}
                    client.record_answer = Mock(side_effect=AssertionError("must not answer"))
                    client._load_answers_json = Mock(return_value={f"q{i}": [] for i in range(43)})
                    client.api.exam_list_plan.return_value = {"code": "0", "data": [{
                        "id": "plan", "examPlanId": "exam", "examPlanName": "test",
                        "examOddNum": 3, "examFinishNum": 0,
                    }]}
                    client.api.exam_before_paper.return_value = {"code": "0"}
                    client.api.exam_prepare_paper.return_value = {"code": "0", "data": {
                        "questionNum": 50, "realName": "test", "userIDLabel": "test",
                        "paperScore": 100, "answerTime": 60,
                    }}
                    client.api.exam_start_paper.return_value = {"code": "0", "data": {
                        "questionList": [{"title": f"q{i}"} for i in range(50)],
                    }}
                    client.run_exam(
                        exam_mode=mode, random_answer=random_answer,
                        exam_submit_match_rate=100,
                        only_project={"projectName": "test", "userProjectId": "project"},
                    )
                    client.api.exam_start_paper.assert_called_once()
                    client.record_answer.assert_not_called()
                    client.api.exam_submit_paper.assert_not_called()
                    client.log.error.assert_called_once()


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

