from dags.multi_sport_betting_workflow import update_elo_ratings
import sys
# fake context
try:
    update_elo_ratings(sport="tennis", elo_ratings={}, config=None, previous_ratings={})
except Exception as e:
    print(f"Error: {e}")
