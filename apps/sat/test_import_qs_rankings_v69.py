"""V69: official QS exports can extend and refresh the university catalogue."""
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.sat.management.commands.import_qs_rankings import normalise, parse_rank
from apps.sat.models import DreamUniversity

CSV = """Rank,Institution,Location,City
1,Massachusetts Institute of Technology (MIT),United States,Cambridge
=8,ETH Zurich,Switzerland,Zürich
250,Example Central Asia University,Kazakhstan,Astana
601-610,Example Banded University,Uzbekistan,Tashkent
,No Rank University,France,Paris
"""


class ParseTests(SimpleTestCase):
    def test_ranks_ties_and_bands(self):
        self.assertEqual(parse_rank("1"), (1, "1"))
        self.assertEqual(parse_rank("=8"), (8, "=8"))
        self.assertEqual(parse_rank("601-610"), (601, "601-610"))
        self.assertEqual(parse_rank("1201–1400"), (1201, "1201–1400"))
        self.assertEqual(parse_rank(""), (None, ""))

    def test_name_normalisation_ignores_filler_words_and_accents(self):
        self.assertEqual(normalise("The University of Tokyo"), normalise("University of Tokyo"))
        self.assertEqual(normalise("École Polytechnique"), normalise("Ecole Polytechnique"))


class ImportCommandTests(TestCase):
    def setUp(self):
        DreamUniversity.objects.all().delete()
        self.mit = DreamUniversity.objects.create(name="Massachusetts Institute of Technology (MIT)",
                                                  country="United States", qs_rank=2, ranking_year=2026)
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "qs.csv"
        self.path.write_text(CSV, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_changes_nothing(self):
        out = StringIO()
        call_command("import_qs_rankings", str(self.path), "--year", "2027", stdout=out)
        self.assertIn("Dry run", out.getvalue())
        self.mit.refresh_from_db()
        self.assertEqual(self.mit.qs_rank, 2)
        self.assertEqual(DreamUniversity.objects.count(), 1)

    def test_apply_updates_existing_and_adds_new_within_max_rank(self):
        call_command("import_qs_rankings", str(self.path), "--year", "2027", "--max-rank", "500",
                     "--apply", stdout=StringIO())
        self.mit.refresh_from_db()
        self.assertEqual((self.mit.qs_rank, self.mit.ranking_year), (1, 2027))
        self.assertTrue(DreamUniversity.objects.filter(name="ETH Zurich", qs_rank=8).exists())
        added = DreamUniversity.objects.get(name="Example Central Asia University")
        self.assertEqual((added.qs_rank, added.city, added.country), (250, "Astana", "Kazakhstan"))
        self.assertFalse(DreamUniversity.objects.filter(name="Example Banded University").exists())
        self.assertFalse(DreamUniversity.objects.filter(name="No Rank University").exists())

    def test_higher_max_rank_includes_banded_rows(self):
        call_command("import_qs_rankings", str(self.path), "--year", "2027", "--max-rank", "1000",
                     "--apply", stdout=StringIO())
        banded = DreamUniversity.objects.get(name="Example Banded University")
        self.assertEqual(banded.qs_rank, 601)
        self.assertIn("601-610", banded.score_note)
