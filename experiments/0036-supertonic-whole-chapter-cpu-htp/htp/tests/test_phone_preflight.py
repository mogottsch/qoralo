import subprocess
from pathlib import Path
import unittest


class TemperatureParserTests(unittest.TestCase):
    def test_only_current_numeric_temperature(self):
        # Samsung dumps may also contain history rows mentioning temperature.
        sample='Current Battery Service state:\n  temperature: 282\n  00:00:01.000 temperature: old\n  temperature-history: ignored\n'
        awk=r'/^[[:space:]]*temperature:/{print $2; exit}'
        result=subprocess.run(['awk',awk],input=sample,text=True,capture_output=True,check=True)
        self.assertEqual(result.stdout,'282\n')
        script=Path(__file__).resolve().parents[1]/'tools/run_phone.sh'
        self.assertIn(r'/^[[:space:]]*temperature:/{print \$2; exit}',script.read_text())

    def test_history_only_does_not_pass(self):
        result=subprocess.run(['awk',r'/^[[:space:]]*temperature:/{print $2; exit}'],
                              input='  00:00:01.000 temperature: 282\n',text=True,capture_output=True,check=True)
        self.assertEqual(result.stdout,'')


if __name__=='__main__':unittest.main()
