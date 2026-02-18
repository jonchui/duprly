#!/usr/bin/env python3
"""
DUPR Rating Impact Predictor
Uses the fitted model to predict rating changes for matches.
"""

import json
from pathlib import Path

class DuprPredictor:
    def __init__(self, model_file='dupr_model.json'):
        """Load the fitted DUPR model"""
        with open(model_file) as f:
            model = json.load(f)
        self.K = model['K']
        self.scale = model['scale']
        # Reliability function parameters (if fitted, otherwise use defaults)
        self.reliability_func = model.get('reliability_func', 'inverse')
        self.reliability_params = model.get('reliability_params', {})
    
    def reliability_multiplier(self, reliability):
        """
        Calculate reliability multiplier g(reliability)
        Lower reliability = larger multiplier (new players move more)
        
        Args:
            reliability: Reliability score (0-100, typically)
        
        Returns:
            Multiplier for impact calculation
        """
        if reliability is None:
            # Default to average reliability if not provided
            reliability = 50
        
        if self.reliability_func == 'inverse':
            # g(rel) = 1 / (1 + rel/100)
            return 1.0 / (1.0 + reliability / 100.0)
        elif self.reliability_func == 'linear':
            # g(rel) = 2 - rel/100, capped at 0.1 and 2.0
            multiplier = 2.0 - (reliability / 100.0)
            return max(0.1, min(2.0, multiplier))
        elif self.reliability_func == 'custom':
            # Use custom parameters if provided
            a = self.reliability_params.get('a', 1.0)
            b = self.reliability_params.get('b', 100.0)
            return a / (1.0 + reliability / b)
        else:
            # Default: inverse
            return 1.0 / (1.0 + reliability / 100.0)
    
    def expected_games(self, r1, r2, r3, r4):
        """
        Calculate expected games for team 1 (players r1, r2) vs team 2 (r3, r4)
        Returns expected games for team 1
        """
        team1_avg = (r1 + r2) / 2
        team2_avg = (r3 + r4) / 2
        rating_diff = team1_avg - team2_avg
        prob_win = 1 / (1 + 10 ** (-rating_diff * self.scale / 400))
        return prob_win * 22  # Typical match is ~22 total games
    
    def predict_impacts(self, r1, r2, r3, r4, games1, games2, winner, 
                        rel1=None, rel2=None, rel3=None, rel4=None):
        """
        Predict rating impacts for all 4 players
        
        Args:
            r1, r2: Pre-match ratings for team 1 players
            r3, r4: Pre-match ratings for team 2 players
            games1, games2: Games scored by each team
            winner: 1 if team 1 won, 2 if team 2 won
            rel1, rel2, rel3, rel4: Reliability scores (0-100) for each player (optional)
        
        Returns:
            (imp1, imp2, imp3, imp4): Predicted impacts for each player
        """
        expected_g1 = self.expected_games(r1, r2, r3, r4)
        actual_g1 = games1
        result_diff = actual_g1 - expected_g1
        
        # Calculate reliability multipliers
        g1 = self.reliability_multiplier(rel1)
        g2 = self.reliability_multiplier(rel2)
        g3 = self.reliability_multiplier(rel3)
        g4 = self.reliability_multiplier(rel4)
        
        if winner == 1:
            # Team 1 won
            return (
                self.K * result_diff * 0.5 * g1,  # Player 1
                self.K * result_diff * 0.5 * g2,  # Player 2
                -self.K * result_diff * 0.5 * g3,  # Player 3
                -self.K * result_diff * 0.5 * g4   # Player 4
            )
        else:
            # Team 2 won
            return (
                -self.K * result_diff * 0.5 * g1,  # Player 1
                -self.K * result_diff * 0.5 * g2,  # Player 2
                self.K * result_diff * 0.5 * g3,   # Player 3
                self.K * result_diff * 0.5 * g4    # Player 4
            )
    
    def predict_match(self, match_data):
        """
        Predict impacts for a match (dict with keys: r1, r2, r3, r4, games1, games2, winner,
        and optionally rel1, rel2, rel3, rel4)
        """
        return self.predict_impacts(
            match_data['r1'], match_data['r2'], match_data['r3'], match_data['r4'],
            match_data['games1'], match_data['games2'], match_data['winner'],
            rel1=match_data.get('rel1'), rel2=match_data.get('rel2'),
            rel3=match_data.get('rel3'), rel4=match_data.get('rel4')
        )

if __name__ == "__main__":
    # Example usage
    predictor = DuprPredictor()
    
    # Example match: Team 1 (4.5, 4.3) vs Team 2 (4.2, 4.0), Team 1 wins 11-7
    r1, r2, r3, r4 = 4.5, 4.3, 4.2, 4.0
    games1, games2 = 11, 7
    winner = 1
    
    exp_games = predictor.expected_games(r1, r2, r3, r4)
    imp1, imp2, imp3, imp4 = predictor.predict_impacts(r1, r2, r3, r4, games1, games2, winner)
    
    print("Example Prediction:")
    print(f"  Team 1: {r1:.2f} & {r2:.2f} vs Team 2: {r3:.2f} & {r4:.2f}")
    print(f"  Score: {games1}-{games2}, Winner: Team {winner}")
    print(f"  Expected games Team 1: {exp_games:.2f}")
    print(f"  Predicted impacts:")
    print(f"    Player 1: {imp1:+.6f}")
    print(f"    Player 2: {imp2:+.6f}")
    print(f"    Player 3: {imp3:+.6f}")
    print(f"    Player 4: {imp4:+.6f}")