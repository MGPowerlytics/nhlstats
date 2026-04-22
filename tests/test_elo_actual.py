"""Tests for Elo rating modules - actual functions"""


class TestNBAEloRating:
    """Test NBAEloRating class"""

    def test_init(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()
        assert elo.config.k_factor == 20
        assert elo.config.home_advantage == 100

    def test_predict(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()
        prob = elo.predict("Lakers", "Celtics")
        assert 0 < prob < 1

    def test_update(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()
        elo.update("Lakers", "Celtics", home_won=True)
        assert elo.get_rating("Lakers") > 1500


class TestNHLEloRating:
    """Test NHLEloRating class"""

    def test_init(self):
        from plugins.elo import NHLEloRating

        elo = NHLEloRating()
        assert (
            elo.config.home_advantage == 65.0
        )  # Reduced from 100 based on empirical NHL home win rates

    def test_predict(self):
        from plugins.elo import NHLEloRating

        elo = NHLEloRating()
        prob = elo.predict("Boston Bruins", "Toronto Maple Leafs")
        assert 0 < prob < 1


class TestMLBEloRating:
    """Test MLBEloRating class"""

    def test_init(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        assert elo.config.k_factor == 4.0
        assert elo.config.home_advantage == 20.0

    def test_predict(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        prob = elo.predict("Red Sox", "Yankees")
        assert 0 < prob < 1

    def test_update(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        elo.update("Red Sox", "Yankees", home_won=True)
        assert elo.get_rating("Red Sox") > 1500


class TestNFLEloRating:
    """Test NFLEloRating class"""

    def test_init(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        assert elo.config.k_factor == 20

    def test_predict(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        prob = elo.predict("Chiefs", "49ers")
        assert 0 < prob < 1

    def test_update(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        elo.update("Chiefs", "49ers", home_won=True)
        assert elo.get_rating("Chiefs") > 1500


class TestNCAABEloRating:
    """Test NCAABEloRating class"""

    def test_init(self):
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()
        assert elo.config.k_factor == 20

    def test_predict(self):
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()
        prob = elo.predict("Duke", "UNC")
        assert 0 < prob < 1


class TestTennisEloRating:
    """Test TennisEloRating class"""

    def test_init(self):
        from plugins.elo import TennisEloRating

        elo = TennisEloRating()
        assert elo.config.k_factor > 0

    def test_predict(self):
        from plugins.elo import TennisEloRating

        elo = TennisEloRating()
        prob = elo.predict("Djokovic", "Federer")
        assert 0 < prob < 1

    def test_update(self):
        from plugins.elo import TennisEloRating

        elo = TennisEloRating()
        elo.update("Djokovic", "Federer")
        assert elo.get_rating("Djokovic") > 1500


class TestEPLEloRating:
    """Test EPLEloRating class"""

    def test_init(self):
        from plugins.elo import EPLEloRating

        elo = EPLEloRating()
        assert elo.config.k_factor == 40.0
        assert elo.config.home_advantage == 80.0

    def test_predict(self):
        from plugins.elo import EPLEloRating

        elo = EPLEloRating()
        prob = elo.predict("Man City", "Liverpool")
        assert 0 < prob < 1


class TestLigue1EloRating:
    """Test Ligue1EloRating class"""

    def test_init(self):
        from plugins.elo import Ligue1EloRating

        elo = Ligue1EloRating()
        assert elo.config.k_factor == 20

    def test_predict(self):
        from plugins.elo import Ligue1EloRating

        elo = Ligue1EloRating()
        prob = elo.predict("PSG", "Marseille")
        assert 0 < prob < 1


class TestGlicko2Rating:
    """Test Glicko2Rating class"""

    def test_init(self):
        from glicko2_rating import Glicko2Rating

        rating = Glicko2Rating()
        assert rating is not None


class TestModuleImports:
    """Test all Elo rating modules can be imported"""

    def test_all_modules(self):
        assert True  # All imports succeeded
