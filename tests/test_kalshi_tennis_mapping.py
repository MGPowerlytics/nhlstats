import unittest
import re
from pathlib import Path
import sys

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))

def get_last_name_code(full_name):
    """
    Extracted from plugins/kalshi_markets.py for testing.
    The rule: first 3 letters of the athlete's last name.
    """
    if not full_name: return ""
    parts = full_name.strip().split()
    last_name = parts[-1] if parts else full_name
    return last_name[:3].upper()

class TestKalshiTennisMapping(unittest.TestCase):
    """
    Ensures that for tennis markets on Kalshi, the last 3 letters
    of the ticker code match the first 3 letters of the athlete's last name.
    """

    def test_ticker_suffix_matches_last_name_code(self):
        # Sample data from recent real runs
        test_cases = [
            # Ticker, Full Name, Expected Code
            ("KXATPMATCH-26JAN20ALCHAN-ALC", "Carlos Alcaraz", "ALC"),
            ("KXWTAMATCH-26JAN20SAKAND-AND", "Mirra Andreeva", "AND"),
            ("KXATPMATCH-26JAN20MAEDJO-DJO", "Novak Djokovic", "DJO"),
            ("KXWTAMATCH-26JAN20GAUDAN-GAU", "Coco Gauff", "GAU"),
            ("KXATPMATCH-26JAN21DUCSIN-SIN", "Jannik Sinner", "SIN"),
            ("KXWTAMATCH-26JAN20BOUSWI-SWI", "Iga Swiatek", "SWI"),
            ("KXATPMATCH-26JAN21MACTSI-TSI", "Stefanos Tsitsipas", "TSI"),
            ("KXATPMATCH-26JAN20ZVEMUL-MUL", "Gilles Muller", "MUL"), # Muller vs Zverev
            ("KXATPCHALLENGERMATCH-26JAN20RIBBLA-BLA", "Darwin Blanch", "BLA"),
            ("KXATPCHALLENGERMATCH-26JAN20RIBBLA-RIB", "Michele Ribecai", "RIB"),
        ]

        for ticker, name, expected_code in test_cases:
            suffix = ticker.split('-')[-1]
            actual_code = get_last_name_code(name)

            with self.subTest(ticker=ticker, name=name):
                self.assertEqual(suffix, expected_code,
                                 f"Ticker suffix {suffix} should match code {expected_code} for {name}")
                self.assertEqual(actual_code, expected_code,
                                 f"Computed code {actual_code} should be {expected_code} for {name}")

    def test_market_title_parsing(self):
        """
        Ensure our regex correctly extracts names from titles.
        """
        # Titles seen in the wild
        titles = [
            ("Will Stefanos Tsitsipas win the Machac vs Tsitsipas : Round Of 64 match?", "Stefanos Tsitsipas"),
            ("Will Michele Ribecai win the Ribecai vs Blanch : Round Of 16 match?", "Michele Ribecai"),
            ("Will Naomi Osaka win the Osaka vs Cirstea : Round Of 64 match?", "Naomi Osaka"),
            ("Will Iga Swiatek win the Bouzkova vs Swiatek match?", "Iga Swiatek"),
        ]

        for title, expected_winner in titles:
            # Simple extraction of the winner (the name after "Will " and before " win")
            match = re.search(r"Will (.*?) win", title)
            self.assertTrue(match, f"Failed to find winner in {title}")
            winner = match.group(1).strip()
            self.assertEqual(winner, expected_winner)

            # Extraction of the two players in the "X vs Y" part
            match_vs = re.search(r"win the (.*?) vs (.*?) (?:match|:)", title)
            if not match_vs:
                match_vs = re.search(r"win the (.*?) vs (.*?) match", title)

            self.assertTrue(match_vs, f"Failed to find matchup in {title}")
            p1 = match_vs.group(1).strip()
            p2 = match_vs.group(2).strip()
            if p2.endswith(' match'): p2 = p2[:-6].strip()

            # Verify the winner's last name code is one of the two players' last name codes
            w_code = get_last_name_code(winner)
            p1_code = get_last_name_code(p1)
            p2_code = get_last_name_code(p2)
            self.assertIn(w_code, [p1_code, p2_code], f"Winner code {w_code} ({winner}) not in matchup codes [{p1_code}, {p2_code}] ({p1} vs {p2})")

if __name__ == "__main__":
    unittest.main()
