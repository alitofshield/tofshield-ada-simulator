from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import h5py
import numpy as np

import server


class TeamShareImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = server.app.test_client()

    @staticmethod
    def _synthetic_hdf5(directory: Path) -> bytes:
        fixture = directory / "team-share-test.h5"
        with h5py.File(fixture, "w") as hdf5_file:
            spectra = hdf5_file.create_group("FullSpectra")
            spectra.create_dataset("MassAxis", data=np.linspace(40, 60, 64))
            spectra.create_dataset("SumSpectrum", data=np.arange(64, dtype=float))
        return fixture.read_bytes()

    def test_private_stream_is_validated_registered_and_removed_on_close(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            upload_root = Path(temporary_directory) / "uploads"
            upload_root.mkdir()
            body = self._synthetic_hdf5(Path(temporary_directory))

            with patch.object(server, "UPLOAD_ROOT", upload_root):
                response = self.client.post(
                    "/api/internal/team-share-import",
                    data=body,
                    content_type="application/octet-stream",
                    headers={
                        "X-ADA-Internal-Import": "team-share-worker",
                        "X-ADA-Team-Share-Key": "12%20component%20mix%2Fsample.h5",
                    },
                )

                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                file_id = payload["file_id"]
                registered = server._get_open_file(file_id)
                self.assertEqual(payload["manifest"]["file"]["provenance"], "Team Share/R2")
                self.assertEqual(registered.provenance, "Team Share/R2")
                self.assertTrue(registered.owned_upload)
                self.assertTrue(registered.path.exists())
                self.assertEqual(list(upload_root.glob("*.part")), [])

                closed = self.client.delete(f"/api/file/{file_id}")
                self.assertEqual(closed.status_code, 200)
                self.assertFalse(registered.path.exists())

    def test_invalid_stream_is_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            upload_root = Path(temporary_directory) / "uploads"
            upload_root.mkdir()

            with patch.object(server, "UPLOAD_ROOT", upload_root):
                response = self.client.post(
                    "/api/internal/team-share-import",
                    data=b"not an hdf5 file",
                    content_type="application/octet-stream",
                    headers={
                        "X-ADA-Internal-Import": "team-share-worker",
                        "X-ADA-Team-Share-Key": "invalid.h5",
                    },
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(list(upload_root.iterdir()), [])

    def test_missing_internal_marker_is_hidden(self) -> None:
        response = self.client.post(
            "/api/internal/team-share-import",
            data=b"ignored",
            headers={"X-ADA-Team-Share-Key": "sample.h5"},
        )
        self.assertEqual(response.status_code, 404)

    def test_size_limit_rejects_stream_and_removes_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            upload_root = Path(temporary_directory) / "uploads"
            upload_root.mkdir()

            with (
                patch.object(server, "UPLOAD_ROOT", upload_root),
                patch.dict(server.app.config, {"MAX_CONTENT_LENGTH": 8}),
            ):
                response = self.client.post(
                    "/api/internal/team-share-import",
                    data=b"0123456789",
                    content_type="application/octet-stream",
                    headers={
                        "X-ADA-Internal-Import": "team-share-worker",
                        "X-ADA-Team-Share-Key": "oversized.h5",
                    },
                )

                self.assertEqual(response.status_code, 413)
                self.assertEqual(list(upload_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
