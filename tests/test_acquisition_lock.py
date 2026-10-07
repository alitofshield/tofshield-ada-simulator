import json, tempfile, unittest
from pathlib import Path
import h5py
import server
from acquisition_context import recorded_context

class AcquisitionLockTests(unittest.TestCase):
    def test_missing_values_do_not_become_demo_defaults(self):
        c=recorded_context({'instrument':[]},server.FIELDS)
        for field in ['reagent','targets','environment','state']:
            self.assertIsNone(c[field]['value']);self.assertEqual(c[field]['status'],'Not recorded')
        self.assertTrue(all(v['value'] is None for v in c['settings'].values()))

    def test_recorded_identity_ignores_calibration_and_background(self):
        def e(path,name,value):return {'path':path,'name':name,'value':value}
        c=recorded_context({'instrument':[e('/Instrument','Reagent_Ion','I-'),e('/Sample','Targets','ACETONE'),e('/Environment','Compounds','N2, O2'),e('/ADA/DetectionCapability','Analyte','BENZENE'),e('/Background','Compounds','CO2')]},server.FIELDS)
        self.assertEqual(c['reagent']['value'],'I-');self.assertEqual(c['targets']['value'],'ACETONE');self.assertEqual(c['environment']['value'],'N2, O2')

    def test_conflicting_values_remain_ambiguous(self):
        c=recorded_context({'instrument':[{'path':'/A','name':'Reagent_Ion','value':'I-'},{'path':'/B','name':'Reagent_Ion','value':'NO3-'}]},server.FIELDS)
        self.assertIsNone(c['reagent']['value']);self.assertIn('Multiple',c['reagent']['status'])

    def test_imported_file_cannot_be_transformed_or_exported_as_simulation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'measured.h5'
            with h5py.File(p,'w') as f:
                g=f.create_group('FullSpectra');g.create_dataset('MassAxis',data=[1.,2.,3.,4.,5.]);g.create_dataset('SumSpectrum',data=[0.,1.,5.,1.,0.])
                f.attrs['Reagent_Ion']='I-'
            file_id,manifest=server._register_file(p,p.name,'assessment table')
            self.assertTrue(manifest['acquisition_locked']);self.assertEqual(manifest['acquisition_context']['reagent']['value'],'I-')
            client=server.app.test_client();base='/api/file/'+file_id
            self.assertEqual(client.get(base+'/spectrum').status_code,200)
            for end in ['/spectrum','/export.csv']:
                r=client.get(base+end,query_string={'instrument_configuration':json.dumps({'gain':2})})
                self.assertEqual(r.status_code,400);self.assertIn('locked',r.json['error'])
            with h5py.File(p) as f:self.assertEqual(f.attrs['Reagent_Ion'],'I-')

    def test_synthetic_workflow_remains_editable(self):
        r=server.app.test_client().post('/api/open-fixture')
        self.assertFalse(r.json['manifest']['acquisition_locked'])

    def test_offline_guide_assets_and_three_categories(self):
        c=server.app.test_client()
        for filename in ['guide.html','guide.css','guide.js','guide.md']:
            r=c.get('/static/'+filename);self.assertEqual(r.status_code,200);r.close()
        page=(server.STATIC_ROOT/'guide.html').read_text()
        self.assertEqual(page.count('<h2 '),3)
        self.assertIn('instrument-svg',page)
        self.assertNotIn('ANIMATION_SLOT',page)
        self.assertIn('FWHM',page)
