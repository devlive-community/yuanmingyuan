"""test_units.py — units.py 单测：斗口等第、营造尺换算、举架剖面。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))

from generator import units  # noqa: E402


class DoukouGradeTests(unittest.TestCase):
    """斗口十一等（出处：《工程做法则例》斗科用材定例）。"""

    def test_eleven_grades_from_6_to_1_cun(self):
        self.assertEqual(len(units.DOUKOU_GRADES_CUN), 11)
        self.assertEqual(units.DOUKOU_GRADES_CUN[0], 6.0)   # 一等 6 寸
        self.assertEqual(units.DOUKOU_GRADES_CUN[-1], 1.0)  # 十一等 1 寸
        for a, b in zip(units.DOUKOU_GRADES_CUN, units.DOUKOU_GRADES_CUN[1:]):
            self.assertAlmostEqual(a - b, 0.5)              # 每等差半寸

    def test_grade_lookup(self):
        self.assertEqual(units.doukou_cun(1), 6.0)
        self.assertEqual(units.doukou_cun(7), 3.0)
        self.assertEqual(units.doukou_cun(11), 1.0)
        with self.assertRaises(ValueError):
            units.doukou_cun(0)
        with self.assertRaises(ValueError):
            units.doukou_cun(12)

    def test_doukou_cm(self):
        self.assertAlmostEqual(units.doukou_cm(7), 3.0 * 3.2)
        self.assertAlmostEqual(units.doukou_cm(1), 6.0 * 3.2)


class ConversionTests(unittest.TestCase):
    """营造尺 / 寸换算（可配置常量）。"""

    def test_chi_to_cm(self):
        self.assertAlmostEqual(units.chi_to_cm(1.0), 32.0)

    def test_cun_to_cm(self):
        self.assertAlmostEqual(units.cun_to_cm(1.0), 3.2)
        self.assertAlmostEqual(units.cun_to_cm(10.0), units.chi_to_cm(1.0))


class JuajiProfileTests(unittest.TestCase):
    """举架剖面（檐步五举起，逐步递增；步架均分为简化，S-003）。"""

    def test_four_steps_profile(self):
        half = 88.5  # 斗口
        pts = units.juaji_profile(half, 4)
        self.assertEqual(len(pts), 5)
        self.assertEqual(pts[0], (0.0, 0.0))  # 檐口
        self.assertAlmostEqual(pts[-1][0], half)
        expected_h = (half / 4) * (0.5 + 0.65 + 0.75 + 0.9)
        self.assertAlmostEqual(pts[-1][1], expected_h)
        # 折线单调：自檐口向脊 x、y 均递增
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            self.assertGreater(x1, x0)
            self.assertGreater(y1, y0)

    def test_two_steps_profile(self):
        pts = units.juaji_profile(10.0, 2)
        self.assertEqual(len(pts), 3)
        self.assertAlmostEqual(pts[-1][1], 5.0 * 0.5 + 5.0 * 0.9)

    def test_unsupported_steps_raises(self):
        with self.assertRaises(ValueError):
            units.juaji_profile(100.0, 5)


if __name__ == "__main__":
    unittest.main()
