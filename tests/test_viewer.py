from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import re

import h5py
import numpy as np

import server


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not server.FIXTURE_PATH.exists():
            from scripts.generate_fixture import main

            main()
        cls.client = server.app.test_client()

    def test_health(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_version_and_detection_endpoint(self) -> None:
        self.assertEqual(self.client.get("/api/config").get_json()["version"], "0.4.6")
        response = self.client.post("/api/detection-capability", json={
            "method": "calibration", "analyte": "TNT", "quantifier_mz": 227.0183,
            "mz_tolerance": 0.05, "concentration_unit": "ppb", "matrix": "Air",
            "calibration": [
                {"concentration": 0, "response": 10},
                {"concentration": 1, "response": 110},
                {"concentration": 2, "response": 210},
            ],
            "blanks": [9, 10, 11],
        })
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.get_json()["loq"], response.get_json()["lod"])

    def test_fixture_inventory_detects_standard_pair(self) -> None:
        manifest = server.inspect_hdf5(
            server.FIXTURE_PATH,
            server.FIXTURE_PATH.name,
            "synthetic example",
        )
        self.assertGreater(manifest["file"]["dataset_count"], 3)
        recommended = manifest["spectrum_candidates"][0]
        self.assertEqual(recommended["x_path"], "/FullSpectra/MassAxis")
        self.assertEqual(recommended["y_path"], "/FullSpectra/SumSpectrum")

    def test_fixture_api_returns_full_and_focused_spectrum(self) -> None:
        opened = self.client.post("/api/open-fixture")
        self.assertEqual(opened.status_code, 200)
        payload = opened.get_json()
        file_id = payload["file_id"]
        candidate = payload["manifest"]["recommended_candidate_id"]

        full = self.client.get(
            f"/api/file/{file_id}/spectrum",
            query_string={"candidate": candidate, "max_points": 5000},
        )
        self.assertEqual(full.status_code, 200)
        full_data = full.get_json()
        self.assertGreater(full_data["raw_point_count"], 20_000)
        self.assertLessEqual(full_data["displayed_point_count"], 5_000)

        focused = self.client.get(
            f"/api/file/{file_id}/spectrum",
            query_string={
                "candidate": candidate,
                "x_min": 278.5,
                "x_max": 280.0,
                "max_points": 10_000,
            },
        )
        self.assertEqual(focused.status_code, 200)
        focused_data = focused.get_json()
        self.assertGreaterEqual(focused_data["range"]["min"], 278.5)
        self.assertLessEqual(focused_data["range"]["max"], 280.0)
        self.assertGreater(len(focused_data["peaks"]), 0)
        for key in ("centroid_mz", "fwhm", "resolving_power", "quality"):
            self.assertIn(key, focused_data["peaks"][0])

    def test_fwhm_and_resolving_power_for_gaussian_peak(self) -> None:
        x = np.linspace(99.9, 100.1, 20_001)
        sigma = 0.004
        y = 12 + 1_000 * np.exp(-0.5 * ((x - 100.0) / sigma) ** 2)
        peak = server._top_peaks(x, y, limit=1, mass_axis=True)[0]
        expected_fwhm = 2.354820045 * sigma
        self.assertEqual(peak["quality"], "Estimated")
        self.assertAlmostEqual(peak["centroid_mz"], 100.0, places=5)
        self.assertAlmostEqual(peak["fwhm"], expected_fwhm, delta=2e-5)
        self.assertAlmostEqual(
            peak["resolving_power"], 100.0 / expected_fwhm, delta=25
        )

    def test_missing_mass_axis_uses_sample_index_and_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "no-axis.h5"
            with h5py.File(path, "w") as file:
                file.create_dataset("SumSpectrum", data=np.arange(200, dtype=np.float64))
            manifest = server.inspect_hdf5(path, path.name, "test")
            candidate = manifest["spectrum_candidates"][0]
            self.assertIsNone(candidate["x_path"])
            self.assertIn("sample index", candidate["warning"])
            self.assertTrue(any("No compatible stored mass axis" in item for item in manifest["warnings"]))

    def test_invalid_hdf5_signature_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid.h5"
            path.write_text("not hdf5", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "valid HDF5 signature"):
                server._validate_hdf5_path(path, require_allowed_root=False)

    def test_file_is_opened_read_only(self) -> None:
        before = server.FIXTURE_PATH.stat().st_mtime_ns
        server.inspect_hdf5(server.FIXTURE_PATH, server.FIXTURE_PATH.name, "test")
        after = server.FIXTURE_PATH.stat().st_mtime_ns
        self.assertEqual(before, after)

    def test_hdf5_string_search_and_session_reset(self) -> None:
        opened = self.client.post("/api/open-fixture").get_json()
        file_id = opened["file_id"]
        response = self.client.get(f"/api/file/{file_id}/search", query_string={"q": "MassAxis"})
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.get_json()["count"], 0)
        closed = self.client.delete(f"/api/file/{file_id}")
        self.assertEqual(closed.status_code, 200)
        expired = self.client.get(f"/api/file/{file_id}/search", query_string={"q": "MassAxis"})
        self.assertEqual(expired.status_code, 400)

    def test_time_series_aggregates_selected_mass_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "time-run.h5"
            mass = np.linspace(50, 60, 101)
            data = np.zeros((12, 2, 101), dtype=np.float32)
            target = np.argmin(abs(mass - 55))
            data[:, :, target] = np.arange(12)[:, None] + 1
            with h5py.File(path, "w") as file:
                group = file.create_group("FullSpectra")
                group.create_dataset("MassAxis", data=mass)
                group.create_dataset("TofData", data=data)
                timing = file.create_group("TimingData")
                timing.create_dataset("BufTimes", data=np.arange(12, dtype=float)[:, None])
            file_id, manifest = server._register_file(path, path.name, "test")
            candidate = next(item for item in manifest["spectrum_candidates"] if item["y_path"] == "/FullSpectra/TofData")
            response = self.client.get(f"/api/file/{file_id}/time-series", query_string={
                "candidate": candidate["id"], "mass_min": 54.95, "mass_max": 55.05,
            })
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(len(payload["time"]), 12)
            self.assertGreater(payload["intensity"][-1], payload["intensity"][0])

    def test_time_series_reconstructs_exact_flattened_tofwerk_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "flattened-run.h5"
            writes, segments, samples = 6, 1, 41
            mass = np.linspace(70, 80, samples)
            frames = np.zeros((writes, 2, 4, samples), dtype=np.float32)
            target = int(np.argmin(abs(mass - 77.5)))
            frames[:, :, :, target] = np.arange(1, writes + 1)[:, None, None]
            with h5py.File(path, "w") as file:
                full = file.create_group("FullSpectra")
                full.create_dataset("MassAxis", data=mass)
                full.create_dataset("SumSpectrum", data=frames.sum(axis=(0, 1, 2)))
                full.create_dataset("TofData", data=frames)
                file.attrs["NbrSamples"] = [samples]
                file.attrs["NbrWrites"] = [writes]
                file.attrs["NbrSegments"] = [segments]
                file.create_group("TimingData").create_dataset("BufTimes", data=np.arange(writes, dtype=float))
            file_id, manifest = server._register_file(path, path.name, "test")
            candidate = next(item for item in manifest["spectrum_candidates"] if item["y_path"] == "/FullSpectra/SumSpectrum")
            response = self.client.get(f"/api/file/{file_id}/time-series", query_string={
                "candidate": candidate["id"], "mass_min": 77.4, "mass_max": 77.6,
            })
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["write_count"], writes)
            self.assertEqual(payload["segment_count"], 8)
            self.assertIn("time-resolved TOFWERK acquisition", payload["storage_interpretation"])
            self.assertGreater(payload["intensity"][-1], payload["intensity"][0])

    def test_companion_exact_filename_relationship(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            hdf = root / "20240214_125236.h5"
            report = root / "run-notes.txt"
            with h5py.File(hdf, "w") as file:
                file.create_dataset("MassAxis", data=np.arange(20, dtype=float))
                file.create_dataset("SumSpectrum", data=np.arange(20, dtype=float))
            report.write_text("Cannabinol injection is stored in 20240214_125236.h5", encoding="utf-8")
            manifest = server.inspect_hdf5(hdf, hdf.name, "local path")
            companion = manifest["companion_context"]["files"][0]
            self.assertEqual(companion["relation"], "confirmed")
            self.assertEqual(companion["evidence"][0]["kind"], "exact_filename")

    def test_vocus_generator_creates_openable_downloadable_hdf5(self) -> None:
        response = self.client.post(
            "/api/generate/vocus",
            json={
                "reagent": "NO3-",
                "targets": "TNT,RDX",
                "environment": "H2O,N2,O2,CO2",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["manifest"]["file"]["provenance"], "synthetic generator")
        self.assertEqual(payload["generation_summary"]["reagent"], "NO3-")
        self.assertTrue(payload["manifest"]["spectrum_candidates"])
        download = self.client.get(payload["download_url"])
        self.assertEqual(download.status_code, 200)
        self.assertTrue(download.data.startswith(b"\x89HDF\r\n\x1a\n"))
        download.close()

    def test_generated_hdf5_embeds_detection_capability_provenance(self) -> None:
        study = {
            "method": "calibration", "analyte": "TNT", "formula": "C7H5N3O6",
            "quantifier_mz": 227.0183, "mz_tolerance": 0.05,
            "concentration_unit": "ppb", "matrix": "Air",
            "calibration": [
                {"concentration": 0, "response": 10},
                {"concentration": 1, "response": 110},
                {"concentration": 2, "response": 210},
            ],
            "blanks": [9, 10, 11],
        }
        response = self.client.post("/api/generate/vocus", json={
            "reagent": "NO3-", "targets": "TNT", "environment": "N2,O2",
            "detection_study": study,
        })
        self.assertEqual(response.status_code, 200)
        file_id = response.get_json()["file_id"]
        path = server._get_open_file(file_id).path
        with h5py.File(path, "r") as generated:
            self.assertIn("/ADA/DetectionCapability", generated)
            group = generated["/ADA/DetectionCapability"]
            self.assertEqual(group.attrs["analyte"], "TNT")
            self.assertGreater(group.attrs["loq"], group.attrs["lod"])

    def test_miptof_generator_creates_elemental_spectrum(self) -> None:
        response = self.client.post(
            "/api/generate/miptof",
            json={
                "isotopes": "U-235,U-238,Pu-239",
                "environment": "N2,O2,CO2,Ar,Fe",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["generation_summary"]["instrument"], "mipTOF")
        self.assertIn("U-235", payload["generation_summary"]["isotopes"])
        self.assertTrue(payload["manifest"]["spectrum_candidates"])

    def test_generator_rejects_unknown_reagent_and_isotope(self) -> None:
        bad_reagent = self.client.post(
            "/api/generate/vocus",
            json={"reagent": "mystery", "targets": "TNT", "environment": "N2"},
        )
        self.assertEqual(bad_reagent.status_code, 400)
        bad_isotope = self.client.post(
            "/api/generate/miptof",
            json={"isotopes": "Xx-999", "environment": "N2"},
        )
        self.assertEqual(bad_isotope.status_code, 400)

    def test_frontend_selectors_and_offline_assets(self) -> None:
        html = (server.STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        javascript = (server.STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        html_ids = set(re.findall(r'id="([^"]+)"', html))
        selectors = set(re.findall(r'querySelector\("#([^"]+)"\)', javascript))
        dynamic_popup_ids = {item for item in selectors if item.startswith("p-")} | {"close-popout"}
        self.assertEqual(selectors - html_ids - dynamic_popup_ids, set())
        self.assertNotRegex(html, r'https?://')
        self.assertTrue((server.STATIC_ROOT / "vendor" / "plotly-3.1.0.min.js").exists())

    def test_two_primary_workspaces_and_configuration_definitions(self) -> None:
        html = (server.STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        javascript = (server.STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertEqual(html.count('data-workspace-target='), 3)
        self.assertIn('id="spectrum-workspace"', html)
        self.assertIn('id="configuration-workspace"', html)
        self.assertIn('TOFshield Simulator - Instrument Configurator', html)
        self.assertIn('instrumentFieldDefinitions', javascript)
        for key in ('flow_ml_min', 'reagent_signal', 'pressure_mbar', 'vacuum_mbar',
                    'resolving_power', 'integration_s', 'drift_ppm'):
            self.assertIn(f'{key}:', javascript)

    def test_target_inputs_are_blank_and_context_autoselection_exists(self) -> None:
        html = (server.STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        javascript = (server.STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertRegex(html, r'id="vocus-targets"[^>]*></textarea>')
        self.assertRegex(html, r'id="miptof-isotopes"[^>]*></textarea>')
        self.assertRegex(html, r'id="detection-analyte"[^>]*placeholder=')
        self.assertNotIn('id="detection-analyte" value="TNT"', html)
        self.assertRegex(html, r'id="detection-calibration"[^>]*></textarea>')
        self.assertIn("applyDetectedInstrumentContext", javascript)
        self.assertIn('activateGeneratorPanel("vocus-panel")', javascript)
        self.assertIn('activateGeneratorPanel("miptof-panel")', javascript)

    def test_explicit_hdf5_context_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vocus_path = Path(temp_dir) / "vocus.h5"
            with h5py.File(vocus_path, "w") as file:
                file.attrs["Instrument_Family"] = "Vocus CI-TOF"
                file.attrs["TargetCompounds"] = "TNT,RDX"
                full = file.create_group("FullSpectra")
                full.create_dataset("MassAxis", data=np.linspace(1, 300, 1000))
                full.create_dataset("SumSpectrum", data=np.ones(1000))
            context = server.inspect_hdf5(vocus_path, vocus_path.name, "test")["instrument_context"]
            self.assertEqual(context["family"], "vocus")
            self.assertEqual(context["suggested_targets"], ["TNT", "RDX"])

            mip_path = Path(temp_dir) / "mip.h5"
            with h5py.File(mip_path, "w") as file:
                file.attrs["Instrument_Model"] = "mipTOF"
                file.attrs["TargetIsotopes"] = ["U-235", "U-238"]
                full = file.create_group("FullSpectra")
                full.create_dataset("MassAxis", data=np.linspace(1, 300, 1000))
                full.create_dataset("SumSpectrum", data=np.ones(1000))
            context = server.inspect_hdf5(mip_path, mip_path.name, "test")["instrument_context"]
            self.assertEqual(context["family"], "miptof")
            self.assertEqual(context["suggested_targets"], ["U-235", "U-238"])

    def test_no_explicit_identity_leaves_targets_empty(self) -> None:
        context = server.inspect_hdf5(server.FIXTURE_PATH, server.FIXTURE_PATH.name, "test")["instrument_context"]
        self.assertEqual(context["suggested_targets"], [])

    def test_generic_analyte_type_and_detection_study_are_not_sample_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mip-context.h5"
            with h5py.File(path, "w") as file:
                file.attrs["Instrument_Family_Simulated"] = "mipTOF"
                instrument = file.create_group("Instrument")
                instrument.attrs["Analyte_Type"] = "Elements and isotopes"
                request = file.create_group("SimulationRequest")
                request.attrs["isotopes"] = "U-235"
                detection = file.create_group("ADA/DetectionCapability")
                detection.attrs["analyte"] = "TNT"
                full = file.create_group("FullSpectra")
                full.create_dataset("MassAxis", data=np.linspace(1, 300, 1000))
                full.create_dataset("SumSpectrum", data=np.ones(1000))
            context = server.inspect_hdf5(path, path.name, "test")["instrument_context"]
            self.assertEqual(context["family"], "miptof")
            self.assertEqual(context["suggested_targets"], ["U-235"])

    def test_fourier_workspace_controls_and_scientific_boundary(self) -> None:
        html = (server.STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        javascript = (server.STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        for control_id in ("dft-mode", "fft-mode", "transform-remove-mean",
                           "transform-hann", "transform-scale", "transform-run",
                           "transform-chart", "transform-summary"):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("cycles per Thomson", html)
        self.assertIn("not flight-time frequency", html)
        self.assertIn("function directDft", javascript)
        self.assertIn("function fastFft", javascript)
        self.assertIn("function uniformSpectrum", javascript)


if __name__ == "__main__":
    unittest.main()
