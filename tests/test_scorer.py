import unittest

from py_doctor.scorer import calculate_score, categorize_issues


class TestScorer(unittest.TestCase):
    def test_perfect_score(self):
        score = calculate_score(errors=0, warnings=0, dead_code=0)
        self.assertEqual(score, 100)

    def test_score_penalties(self):
        # 1 error (-3) + 2 warnings (-2) + 1 dead code (-1) = -6 -> 94
        score = calculate_score(errors=1, warnings=2, dead_code=1)
        self.assertEqual(score, 94)

        # Critical issue penalty: 1 error (-3) + 1 critical (-10) = -13 -> 87
        score_crit = calculate_score(errors=1, warnings=0, dead_code=0, critical_issues=1)
        self.assertEqual(score_crit, 87)

        # Vulnerable dependency: 1 error (-3) + 1 dependency (-15) = -18 -> 82
        score_dep = calculate_score(errors=1, warnings=0, dead_code=0, dependency_issues=1)
        self.assertEqual(score_dep, 82)

    def test_score_clamping(self):
        score_low = calculate_score(errors=100, warnings=100, dead_code=100)
        self.assertEqual(score_low, 0)

        score_high = calculate_score(errors=-10, warnings=0, dead_code=0)
        self.assertEqual(score_high, 100)

    def test_categorize_issues(self):
        diagnostics = [
            {"type": "ERR", "rule": "ruff/E999", "location": "main.py:1"},
            {"type": "WARN", "rule": "ruff/W291", "location": "main.py:2"},
            {"type": "DEAD", "rule": "vulture/dead-code", "location": "main.py:10"},
            {"type": "ERR", "rule": "fastapi/hardcoded-secret", "location": "config.py:5"},
            {"type": "ERR", "rule": "bandit/B105", "location": "config.py:6"},
            {"type": "ERR", "rule": "audit/PYSEC-2023-1", "location": "reqs.txt"},
        ]
        cats = categorize_issues(diagnostics)
        self.assertEqual(cats["errors"], 4)
        self.assertEqual(cats["warnings"], 1)
        self.assertEqual(cats["dead_code"], 1)
        self.assertEqual(cats["critical"], 1)  # fastapi/hardcoded-secret
        self.assertEqual(cats["security"], 2)  # fastapi/hardcoded-secret + bandit/B105
        self.assertEqual(cats["dependencies"], 1)  # audit/PYSEC-2023-1


if __name__ == "__main__":
    unittest.main()
