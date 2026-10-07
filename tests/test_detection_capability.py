from __future__ import annotations

import unittest

from detection_capability import calculate_study, classify_peak


class DetectionCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "analyte": "TNT", "formula": "C7H5N3O6",
            "quantifier_mz": 227.0183, "mz_tolerance": 0.05,
            "concentration_unit": "ppb", "matrix": "Air",
            "method": "calibration",
            "calibration": [
                {"concentration": 0, "response": 18},
                {"concentration": 0.5, "response": 71},
                {"concentration": 1, "response": 123},
                {"concentration": 2, "response": 229},
                {"concentration": 5, "response": 544},
            ],
            "blanks": [17, 20, 16, 19, 18, 21, 17],
        }

    def test_calibration_estimate(self) -> None:
        result = calculate_study(self.payload)
        self.assertGreater(result["lod"], 0)
        self.assertGreater(result["loq"], result["lod"])
        self.assertGreater(result["r_squared"], 0.999)
        self.assertEqual(result["blank_count"], 7)

    def test_signal_noise_estimate(self) -> None:
        result = calculate_study(self.payload | {"method": "signal_noise"})
        self.assertGreater(result["loq_response"], result["lod_response"])
        self.assertIn("3:1", result["method_label"])

    def test_user_supplied_limits(self) -> None:
        result = calculate_study({
            "method": "user_supplied", "analyte": "TNT",
            "quantifier_mz": 227.0183, "mz_tolerance": 0.05,
            "concentration_unit": "ppb", "matrix": "Air",
            "lod": 0.5, "loq": 1.5,
            "validation_status": "User-supplied—not verified by ADA",
        })
        self.assertEqual(result["lod"], 0.5)
        self.assertIsNone(result["slope"])

    def test_peak_classification_and_mass_tolerance(self) -> None:
        result = calculate_study(self.payload)
        outside = classify_peak(228.0, 500, result)
        self.assertEqual(outside["detection_status"], "Not evaluated")
        below = classify_peak(227.0183, result["intercept"], result)
        self.assertEqual(below["detection_status"], "Below LOD")
        quant = classify_peak(227.0183, result["intercept"] + result["slope"] * result["loq"] * 1.2, result)
        self.assertEqual(quant["detection_status"], "Quantifiable")

    def test_invalid_nonpositive_slope_rejected(self) -> None:
        payload = self.payload | {"calibration": [
            {"concentration": 0, "response": 5},
            {"concentration": 1, "response": 4},
            {"concentration": 2, "response": 3},
        ]}
        with self.assertRaisesRegex(ValueError, "slope"):
            calculate_study(payload)


if __name__ == "__main__":
    unittest.main()
