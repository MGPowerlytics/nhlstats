import os
from plugins.elo.tennis_elo_rating import TennisEloRating

elo = TennisEloRating()
elo.update("Player A", "Player B", "ATP")
print(elo.atp_ratings)

elo.update("Player B", "Player A", "WTA")
print(elo.wta_ratings)
