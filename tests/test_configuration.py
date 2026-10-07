import unittest, json, hashlib
import numpy as np
import server
from instrument_config import normalize, transform

class ConfigurationTests(unittest.TestCase):
    def test_bounds_and_invalid_values(self):
        for bad in ({'flow_ml_min':0},{'noise':float('nan')},{'mass_min':600,'mass_max':500}):
            with self.assertRaises(ValueError): normalize(bad)
    def test_delay_gain_dilution_and_fault(self):
        x=np.linspace(50,60,1001); y=np.ones(1001)*100
        a=transform(x,y,normalize({'resolving_power':100000}))[1]
        b=transform(x,y,normalize({'dilution':2,'resolving_power':100000}))[1]
        np.testing.assert_allclose(b,a/2)
        self.assertTrue(np.all(transform(x,y,normalize({'elapsed_s':0}))[1]==0))
        self.assertTrue(np.all(transform(x,y,normalize({'state':'fault'}))[1]==0))
    def test_api_export_and_source_unchanged(self):
        before=hashlib.sha256(server.FIXTURE_PATH.read_bytes()).hexdigest()
        client=server.app.test_client(); opened=client.post('/api/open-fixture').get_json()
        cfg={'mass_min':200,'mass_max':400,'drift_ppm':20,'dilution':2}
        url='/api/file/'+opened['file_id']
        args={'instrument_configuration':json.dumps(cfg),'max_points':5000}
        result=client.get(url+'/spectrum',query_string=args)
        self.assertEqual(result.status_code,200)
        self.assertIsNotNone(result.get_json()['configuration_report'])
        csv=client.get(url+'/export.csv',query_string=args)
        self.assertEqual(csv.status_code,200)
        self.assertIn(b'illustrative configured response',csv.data)
        self.assertEqual(before,hashlib.sha256(server.FIXTURE_PATH.read_bytes()).hexdigest())
    def test_generated_configuration_and_reagent(self):
        c=server.app.test_client()
        r=c.post('/api/generate/vocus',json={'targets':'ACETONE','reagent':'I-','instrument_configuration':{'reagent':'H3O+'}})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.get_json()['generation_summary']['reagent'],'H3O+')
