import pathlib, sys, tempfile, unittest, yaml
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from roleplay_gate import intake,validate,Blocked

class SourceGateTests(unittest.TestCase):
    def test_missing_file_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder)
            (root/"manifest.yaml").write_text(yaml.safe_dump({"version":1,
                "required_files":[{"path":"kaanon.md"}]}))
            with self.assertRaises(Blocked): intake(root)

    def test_spoiler_reverse_and_citation_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder)
            (root/"totuus.md").write_text("terces a si sihT"[::-1])
            (root/"manifest.yaml").write_text(yaml.safe_dump({"version":1,
                "required_files":[{"path":"totuus.md","transform":"reversed_characters"}]}))
            sources=intake(root)
            self.assertEqual(sources[0]["text"],"terces a si sihT")
            with self.assertRaises(Blocked):
                validate({"scene":"A scene","source_receipts":[],"fact_citations":[]},sources)

if __name__=="__main__": unittest.main()
