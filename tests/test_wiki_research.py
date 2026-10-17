import json
import threading
import unittest
from unittest.mock import Mock, patch

from backend.codex_provider import CodexCancelled, CodexError
from backend.wiki_research import PublicResearch


def prompt(room="wangsheng-trio", terms=None):
    return "instructions\n<research_question_data>\n" + json.dumps({"roomId": room, "lookupTerms": terms if terms is not None else ["原神 蓝砚"], "question": ""}) + "\n</research_question_data>"


class WikiResearchTests(unittest.TestCase):
    def setUp(self):
        self.native = Mock()
        self.native.search.return_value = {"summary": "native", "sources": []}
        self.native.status.return_value = {"configured": True, "serviceTier": "fast"}
        self.research = PublicResearch(None, native=self.native)
        self.cancel = threading.Event()

    def test_only_explicit_terms_in_wangsheng_use_wiki(self):
        with patch.object(self.research, "request") as request:
            for value in (prompt("standard"), prompt("zzz-trio"), prompt(terms=[]), prompt(terms=["https://private.invalid"]),
                          "<research_question_data>\n[]\n</research_question_data>", "not-a-prompt"):
                self.assertEqual(self.research.search(value, self.cancel)["summary"], "native")
            request.assert_not_called()
        self.assertEqual(self.research.status()["serviceTier"], "fast")

    def test_wiki_extracts_public_text_with_separate_sources(self):
        responses = [{"query": {"search": [{"pageid": 7, "title": "蓝砚"}]}},
                     {"parse": {"revid": 42, "wikitext": {"*": "蓝砚是人物。\nhttps://example.org/source"}}}]
        with patch.object(self.research, "request", side_effect=responses) as request:
            report = self.research.search(prompt(), self.cancel)
        self.native.search.assert_not_called()
        self.assertEqual(request.call_args_list[0].args[0]["srsearch"], "蓝砚")
        self.assertIn("社区", report["summary"])
        self.assertNotIn("https://", report["summary"])
        self.assertEqual(report["sources"][0]["url"], "https://wiki.biligame.com/ys/index.php?curid=7")

    def test_failure_and_missing_hits_fall_back(self):
        for outcome in (CodexError("network"), {"query": {"search": []}}):
            with patch.object(self.research, "request", side_effect=outcome if isinstance(outcome, Exception) else None,
                              return_value=outcome):
                self.assertEqual(self.research.search(prompt(), self.cancel, deep=True)["summary"], "native")
        self.assertTrue(self.native.search.call_args.kwargs["deep"])

    def test_cancellation_never_starts_fallback(self):
        with patch.object(self.research, "request", side_effect=CodexCancelled("stopped")):
            with self.assertRaises(CodexCancelled):
                self.research.search(prompt(), self.cancel)
        self.native.search.assert_not_called()

    def test_transport_uses_fixed_host_no_proxy_no_redirect(self):
        process = Mock()
        process.communicate.return_value = (b'{}', b'')
        process.returncode = 0
        process.poll.return_value = 0
        with patch("backend.wiki_research.shutil.which", return_value="curl.exe"), patch("backend.wiki_research.subprocess.Popen", return_value=process) as popen:
            self.research.request({"action": "query", "srsearch": "蓝砚"}, self.cancel)
        command = popen.call_args.args[0]
        self.assertEqual(command[1], "--disable")
        self.assertIn("--noproxy", command)
        self.assertNotIn("--proxy", command)
        self.assertNotIn("--location", command)
        self.assertTrue(command[-1].startswith("https://wiki.biligame.com/ys/api.php?"))


if __name__ == "__main__":
    unittest.main()
