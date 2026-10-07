import json, shutil, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import server
import h5py

class ReviewOpenTests(unittest.TestCase):
    def test_review_open_and_instrument_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'HDF5';root.mkdir();static=Path(tmp)/'static';static.mkdir()
            shutil.copy2(server.FIXTURE_PATH,root/'test.h5')
            report={'rows':[{'path':'HDF5/test.h5','instrument':'mipTOF','instrumentBasis':'Reviewed notes'}]}
            (static/'tofwerk-assessment.json').write_text(json.dumps(report))
            with patch.object(server,'ALLOWED_ROOTS',[root]),patch.object(server,'STATIC_ROOT',static):
                client=server.app.test_client()
                response=client.post('/api/open-reviewed',json={'path':'HDF5/test.h5'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json['manifest']['instrument_context']['family'],'vocus')
                with h5py.File(root/'test.h5','w') as f:
                    f.create_dataset('signal',data=[1.,2.,3.])
                response=client.post('/api/open-reviewed',json={'path':'HDF5/test.h5'})
                self.assertEqual(response.json['manifest']['instrument_context']['family'],'miptof')
                self.assertEqual(client.post('/api/open-reviewed',json={'path':'HDF5/../test.h5'}).status_code,400)
                self.assertEqual(client.post('/api/open-reviewed',json={'path':'HDF5/not-listed.h5'}).status_code,400)
                (root/'test.h5').unlink()
                self.assertEqual(client.post('/api/open-reviewed',json={'path':'HDF5/test.h5'}).status_code,404)

    def test_symlink_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'HDF5';root.mkdir();static=Path(tmp)/'static';static.mkdir()
            shutil.copy2(server.FIXTURE_PATH,Path(tmp)/'outside.h5')
            (root/'test.h5').symlink_to(Path(tmp)/'outside.h5')
            (static/'tofwerk-assessment.json').write_text(json.dumps({'rows':[{'path':'HDF5/test.h5','instrument':'mipTOF'}]}))
            with patch.object(server,'ALLOWED_ROOTS',[root]),patch.object(server,'STATIC_ROOT',static):
                self.assertEqual(server.app.test_client().post('/api/open-reviewed',json={'path':'HDF5/test.h5'}).status_code,400)
