import os
from loguru import logger
import click
import json
from dupr_client import DuprClient
from openpyxl import Workbook
from dotenv import load_dotenv
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from dupr_db import open_db, Base, Player, Match, MatchTeam, Rating, MatchDetail

load_dotenv()
dupr = DuprClient()

eng = open_db()
with Session(eng) as sess:
    Base.metadata.create_all(eng)


def ppj(data):
    logger.debug(json.dumps(data, indent=4))


def dupr_auth():
    username = os.getenv("DUPR_USERNAME")
    password = os.getenv("DUPR_PASSWORD")
    dupr.auth_user(username, password)


def get_player_from_dupr(pid: int) -> Player:

    rc, pdata = dupr.get_player(pid)
    logger.debug(f"dupr.get_player for id {pid} GET...")
    ppj(pdata)

    player = None

    with Session(eng) as sess:
        player = Player().from_json(pdata)
        logger.debug(f"{player.dupr_id}, {player.full_name}, {player.rating}")
        Player.save(sess, player)
        sess.commit()

    return player


def get_all_players_from_dupr():
    club_id = os.getenv("DUPR_CLUB_ID")
    _rc, players = dupr.get_members_by_club(club_id)
    for pdata in players:
        with Session(eng) as sess:
            player = Player().from_json(pdata)
            logger.debug(f"{player.id}, {player.full_name}, {player.rating}")
            Player.save(sess, player)
            sess.commit()


def get_matches_from_dupr(dupr_id: int):
    """Get match history for specified player"""

    _rc, matches = dupr.get_member_match_history_p(dupr_id)

    with Session(eng) as sess:

        for mdata in matches:
            print("match")
            ppj(mdata)
            m = Match().from_json(mdata)
            # now we have match, and potentially four new players
            # deal with the fact that player may already exists
            m1 = Match.get_by_id(sess, m.match_id)
            if m1:
                # update
                continue  # skip

            for team in m.teams:
                print(f"team {team}")
                plist = []
                for p in team.players:
                    # This is very kludgy, the player data returned from the MatchHistory
                    # call only has a few fields
                    p1 = sess.execute(
                        select(Player).where(Player.dupr_id == p.dupr_id)
                    ).scalar_one_or_none()
                    if p1:
                        # set team to this player object instead
                        plist.append(p1)
                        print(f"use existing populated player")
                    else:
                        # We need to handle a strange case where the same player
                        # enter himself/herself twice on a doubles team.
                        # If we just add both "new limited (but same)" team members
                        # SQLA seems to happily add both?
                        # so check to see if p already has been added:
                        if len(plist) > 0 and plist[0].dupr_id == p.dupr_id:
                            logger.warning(
                                f"same player on doubles team {p.dupr_id} {m.match_id}"
                            )
                            continue
                        plist.append(p)
                        print(f"saved new limited data player")
                team.players = plist
            sess.add(m)
            sess.commit()


def update_ratings_from_dupr():

    with Session(eng) as sess:
        # Has to use "has" not "any" because it is 1=1? Also need to have something
        # in the has() function
        dupr_ids = sess.scalars(
            select(Player.dupr_id).where(~Player.rating.has(Rating.doubles))
        )

    for i in dupr_ids:
        get_player_from_dupr(i)


@click.command()
def build_match_detail():
    """Flatten match data for faster query"""
    with Session(eng) as sess:
        sess.execute(delete(MatchDetail))
        matches = sess.scalars(select(Match))
        for match in matches:
            print(match)
            md = MatchDetail()
            md.match = match
            t1 = match.teams[0]
            md.team_1_score = t1.score1
            md.team_1_player_1_id = t1.players[0].id
            if len(t1.players) > 1:
                md.team_1_player_2_id = t1.players[1].id
            t2 = match.teams[1]
            md.team_2_score = t2.score1
            md.team_2_player_1_id = t2.players[0].id
            if len(t2.players) > 1:
                md.team_2_player_2_id = t2.players[1].id
            sess.add(md)
            sess.commit()


def match_row(m: Match) -> tuple:
    return (
        m.match_id,
        m.user_id,
        m.display_identity,
        m.event_date,
        m.confirmed,
        m.event_format,
        m.match_type,
    )


def team_row(t: MatchTeam, ratings) -> tuple:
    doubles1 = ratings.get(t.player1.id, ("NA", "NA", "NA"))[2]
    if t.player2:
        doubles2 = ratings.get(t.player2.id, ("NA", "NA", "NA"))[2]
        p2_row = (t.player2.dupr_id, t.player2.full_name, doubles2)
    else:
        doubles2 = "NA"
        p2_row = ("", "", "NA")

    return (
        (t.player1.dupr_id, t.player1.full_name, doubles1) + p2_row + (t.game_score1,)
    )


@click.command()
def write_excel():
    from openpyxl.styles import numbers

    wb = Workbook()
    ws = wb.active
    ws.title = "players"
    # cache all ratings
    player_ratings = {}

    ws.append(
        ("id", "DUPR id", "full name", "gender", "age")
        + ("single", "single verified", "single provisional")
        + ("double", "double verified", "double provisional")
    )

    for d in ptable:
        p = Player().from_json(d)
        ws.append(
            (
                p.id,
                p.dupr_id,
                p.full_name,
                p.gender,
                p.age,
                p.singles,
                p.singles_verified,
                p.singles_provisional,
                p.doubles,
                p.doubles_verified,
                p.doubles_provisional,
            )
        )
        player_ratings[p.id] = (
            p.singles,
            p.singles_verified,
            p.doubles,
            p.doubles_verified,
        )

    col = ws.column_dimensions["A"]
    col.number_format = "#,##0"

    ws = wb.create_sheet("matches")

    prow = (
        "player1 DUPR ID",
        "player 1",
        "player1 doubles",
        "player2 DUPR ID",
        "player 2",
        "player2 doubles",
        "score1",
    )
    ws.append(
        (
            "match id",
            "user_id",
            "match display",
            "event date",
            "confirmed",
            "format",
            "match type",
        )
        + prow
        + prow
    )
    for d in mtable:
        m = Match().from_json(d)
        t1 = m.teams[0]
        t2 = m.teams[1]
        ws.append(
            (
                match_row(m)
                + team_row(m.teams[0], player_ratings)
                + team_row(m.teams[1], player_ratings)
            )
        )

    col = ws.column_dimensions["A"]
    col.number_format = "#,##0"
    col = ws.column_dimensions["B"]
    col.number_format = "#,##0"
    col = ws.column_dimensions["J"]
    col.format = numbers.FORMAT_TEXT

    wb.save(filename="dupr.xlsx")


@click.command()
def stats():
    with Session(eng) as sess:
        c = sess.query(Player).count()
        print(f"number of players {c}")
        c = sess.query(Match).count()
        print(f"number of matches {c}")


@click.command()
@click.argument("pid")
def get_player(pid: int):
    """Get player from DUPR by ID"""
    dupr_auth()
    get_player_from_dupr(pid)


@click.command()
@click.argument("pid")
def delete_player(pid: int):
    """Get player from DUPR if necessary"""
    logger.debug(f"delete player {pid} from database")
    pass


@click.command()
def update_ratings():
    dupr_auth()
    update_ratings_from_dupr()


@click.command()
def test_db():
    dupr_auth()
    club_id = os.getenv("DUPR_CLUB_ID")
    _rc, players = dupr.get_members_by_club(club_id)
    return
    with Session(eng) as sess:
        # Has to use "has" not "any" because it is 1=1? Also need to have something
        # in the has() function
        # use sess.scalars instead of execute(...).scalars() for more concise use
        dupr_ids = sess.scalars(
            select(Player.dupr_id).where(~Player.rating.has(Rating.doubles))
        )
    for i in dupr_ids:
        print(i)


@click.command()
def get_all_players():
    dupr_auth()
    get_all_players_from_dupr()


@click.command()
@click.argument("dupr_id")
def get_matches(dupr_id: int):
    """Get match history for specified player"""
    dupr_auth()
    get_matches_from_dupr(dupr_id)


@click.command()
def get_data():
    """Update all data"""
    logger.info("Getting data from DUPR...")
    dupr_auth()
    get_all_players_from_dupr()
    with Session(eng) as sess:
        for p in sess.execute(select(Player)).scalars():
            get_matches_from_dupr(p.dupr_id)

    update_ratings_from_dupr()

@click.command()
@click.argument("query")
def search_players(query: str):
    """Search for players by name using DUPR search API"""
    dupr_auth()
    
    print(f"🔍 Searching for players matching: '{query}'")
    print("=" * 60)
    
    rc, results = dupr.search_players(query)
    
    if rc == 200 and results:
        hits = results.get('hits', [])
        total = results.get('total', 0)
        
        print(f"Found {total} players matching '{query}':")
        print()
        
        for i, player in enumerate(hits, 1):
            name = player.get('fullName', 'Unknown')
            dupr_id = player.get('duprId', 'Unknown')
            age = player.get('age', 'Unknown')
            location = player.get('shortAddress', 'Unknown')
            distance = player.get('distance', 'Unknown')
            
            ratings = player.get('ratings', {})
            doubles = ratings.get('doubles', 'NR')
            singles = ratings.get('singles', 'NR')
            
            print(f"{i:2d}. {name}")
            print(f"    DUPR ID: {dupr_id}")
            print(f"    Age: {age}, Location: {location}")
            print(f"    Distance: {distance}")
            print(f"    Doubles: {doubles}, Singles: {singles}")
            print()
    else:
        print(f"❌ Search failed or no results found for '{query}'")
        if rc != 200:
            print(f"   Status code: {rc}")




@click.command()
@click.argument("player1_id")
@click.argument("player2_id") 
@click.argument("player3_id")
@click.argument("player4_id")
def expected_score(player1_id: int, player2_id: int, player3_id: int, player4_id: int):
    """Get expected score for a doubles match between two teams"""
    dupr_auth()
    
    teams = [
        {"player1Id": int(player1_id), "player2Id": int(player2_id)},
        {"player1Id": int(player3_id), "player2Id": int(player4_id)}
    ]
    
    print(f"🎯 DUPR Expected Score Prediction")
    print("=" * 50)
    print(f"Team 1: Players {player1_id} & {player2_id}")
    print(f"Team 2: Players {player3_id} & {player4_id}")
    print()
    
    rc, results = dupr.get_expected_score(teams)
    
    if rc == 200 and results:
        teams_result = results.get('teams', [])
        if len(teams_result) >= 2:
            team1_score = teams_result[0].get('score', 'N/A')
            team2_score = teams_result[1].get('score', 'N/A')
            
            print(f"📊 Expected Scores:")
            print(f"  Team 1: {team1_score}")
            print(f"  Team 2: {team2_score}")
            
            # Determine winner
            if isinstance(team1_score, (int, float)) and isinstance(team2_score, (int, float)):
                if team1_score > team2_score:
                    print(f"🏆 Predicted Winner: Team 1")
                elif team2_score > team1_score:
                    print(f"🏆 Predicted Winner: Team 2")
                else:
                    print(f"🤝 Predicted: Tie")
        else:
            print("❌ Invalid response format")
    else:
        print(f"❌ Failed to get expected score (status: {rc})")


@click.group()
def cli():
    pass


if __name__ == "__main__":
    logger.add("duprly_{time}.log")
    cli.add_command(get_data)
    cli.add_command(write_excel)
    cli.add_command(stats)
    cli.add_command(get_all_players)
    cli.add_command(get_player)
    cli.add_command(delete_player)
    cli.add_command(get_matches)
    cli.add_command(update_ratings)
    cli.add_command(build_match_detail)
    cli.add_command(test_db)
    cli.add_command(search_players)
    cli.add_command(expected_score)
    cli.add_command(analyze_matches)
    cli.add_command(create_match_template)
    cli.add_command(analyze_matches)
    cli.add_command(create_match_template)
    cli()
    
    print('🎯 MATCH PREDICTIONS & RATING TARGETS:')
    print('-' * 80)
    
    for match in matches:
        round_name = match.get('round', 'Unknown Round')
        team1 = match.get('team1', [])
        team2 = match.get('team2', [])
        
        print(f'\\n{round_name}')
        print('-' * 50)
        print(f'Team 1: {team1[0]} & {team1[1]}')
        print(f'Team 2: {team2[0]} & {team2[1]}')
        
        # Get player ratings
        team1_ratings = []
        team2_ratings = []
        
        for player in team1:
            if player in player_db:
                team1_ratings.append(player_db[player]['rating'])
            else:
                print(f'  ⚠️  Unknown player: {player}')
                team1_ratings.append(3.0)  # Default rating
        
        for player in team2:
            if player in player_db:
                team2_ratings.append(player_db[player]['rating'])
            else:
                print(f'  ⚠️  Unknown player: {player}')
                team2_ratings.append(3.0)  # Default rating
        
        # Calculate average ratings
        team1_avg = sum(team1_ratings) / len(team1_ratings)
        team2_avg = sum(team2_ratings) / len(team2_ratings)
        
        print(f'  Team 1 Avg Rating: {team1_avg:.3f}')
        print(f'  Team 2 Avg Rating: {team2_avg:.3f}')

@click.command()
@click.argument("match_file")
        
        # Get expected scores from DUPR API
        try:
            team1_numeric = [numeric_ids.get(p, 0) for p in team1]
            team2_numeric = [numeric_ids.get(p, 0) for p in team2]
            
            teams = [
                {'player1Id': team1_numeric[0], 'player2Id': team1_numeric[1]},
                {'player1Id': team2_numeric[0], 'player2Id': team2_numeric[1]}
            ]
            
            rc, results = dupr.get_expected_score(teams)
            
            if rc == 200 and results:
                teams_result = results.get('teams', [])
                if len(teams_result) >= 2:
                    team1_score = teams_result[0].get('score', 'N/A')
                    team2_score = teams_result[1].get('score', 'N/A')
                    
                    print(f'\\n📊 Expected Scores:')
                    print(f'  {team1[0]} & {team1[1]}: {team1_score}')
                    print(f'  {team2[0]} & {team2[1]}: {team2_score}')
                    
                    # Determine winner and rating implications
                    if isinstance(team1_score, (int, float)) and isinstance(team2_score, (int, float)):
                        if team1_score > team2_score:
                            winner = f'{team1[0]} & {team1[1]}'
                            margin = team1_score - team2_score
                            print(f'🏆 Predicted Winner: {winner}')
                            print(f'   Margin: +{margin:.1f} points')
                            
                            # Rating improvement analysis
                            if team1_avg > team2_avg:
                                print(f'   💡 Team 1 favored - win by {margin:.1f}+ for max rating gain')
                            else:
                                print(f'   💡 Team 1 underdog - any win = big rating boost!')
                                
                        elif team2_score > team1_score:
                            winner = f'{team2[0]} & {team2[1]}'
                            margin = team2_score - team1_score
                            print(f'🏆 Predicted Winner: {winner}')
                            print(f'   Margin: +{margin:.1f} points')
                            
                            # Rating improvement analysis
                            if team2_avg > team1_avg:
                                print(f'   💡 Team 2 favored - win by {margin:.1f}+ for max rating gain')
                            else:
                                print(f'   💡 Team 2 underdog - any win = big rating boost!')
                        else:
                            print(f'🤝 Predicted: Tie')
                            print(f'   💡 Very competitive - any win = significant rating boost!')
                else:
                    print('❌ Invalid response format')
            else:
                print(f'❌ Failed to get expected score (status: {rc})')
                
        except Exception as e:
            print(f'❌ Error getting expected score: {e}')
            # Fallback to rating-based prediction
            rating_diff = abs(team1_avg - team2_avg)
            if rating_diff < 0.1:
                print(f'📊 Rating-based prediction: Very close match (diff: {rating_diff:.3f})')
            elif team1_avg > team2_avg:
                print(f'📊 Rating-based prediction: {team1[0]} & {team1[1]} favored')
            else:
                print(f'📊 Rating-based prediction: {team2[0]} & {team2[1]} favored')

@click.command()
def create_match_template():
    """Create a template file for match analysis"""
    template = {
        "matches": [
            {
                "round": "Round 1",
                "team1": ["Player1", "Player2"],
                "team2": ["Player3", "Player4"]
            },
            {
                "round": "Round 2", 
                "team1": ["Player5", "Player6"],
                "team2": ["Player7", "Player8"]
            }
        ]
    }
    
    with open('match_template.json', 'w') as f:
        json.dump(template, f, indent=2)
    
    print('📝 Created match_template.json')
    print('Edit this file with your actual matches and run:')
    print('python3 duprly.py analyze-matches match_template.json')


@click.command()
@click.argument("match_file")
def analyze_matches(match_file: str):
    """Analyze matches from a file and show expected scores and rating targets"""
    import json
    
    dupr_auth()
    
    # Load match data
    try:
        with open(match_file, 'r') as f:
            data = json.load(f)
        matches = data.get('matches', [])
    except FileNotFoundError:
        print(f"❌ File {match_file} not found")
        return
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {match_file}")
        return
    
    print('🏆 MATCH ANALYSIS & RATING IMPROVEMENT TARGETS')
    print('=' * 80)
    
    # Player database
    player_db = {
        'Jonathan Chui': {'dupr_id': '0YVNWN', 'rating': 3.734},
        'Kirk White': {'dupr_id': '3Y5YG3', 'rating': 4.642},
        'Milos Koprivica': {'dupr_id': 'Q5440D', 'rating': 4.163},
        'Robert Kuseski': {'dupr_id': 'M2WJVO', 'rating': 4.100},
        'Thomas Noonan': {'dupr_id': 'N7XNVW', 'rating': 4.151},
        'Michael Fox': {'dupr_id': 'RZVG0E', 'rating': 4.625},
        'Leo Alvarez': {'dupr_id': '6ZLLQQ', 'rating': 3.532},
        'Nick Segura': {'dupr_id': '1NVRLN', 'rating': 3.816},
        'Matthew Stephens': {'dupr_id': 'W6W9OG', 'rating': 4.488},
        'Mike Hedges': {'dupr_id': '3XQMQ5', 'rating': 4.049},
        'Sean Tansey': {'dupr_id': 'W6DE7Y', 'rating': 3.995},
        'John Marcelia': {'dupr_id': 'YN0QR4', 'rating': 4.011}
    }
    
    # Numeric ID mapping for API calls
    numeric_ids = {
        'Jonathan Chui': 4405492894,
        'Kirk White': 7285039969,
        'Milos Koprivica': 4363666385,
        'Robert Kuseski': 5109225170,
        'Thomas Noonan': 5892289277,
        'Michael Fox': 5276996759,
        'Leo Alvarez': 5842721905,
        'Nick Segura': 7856756110,
        'Matthew Stephens': 6468480130,
        'Mike Hedges': 7858246744,
        'Sean Tansey': 8289162435,
        'John Marcelia': 4363666385
    }
    
    print('🎯 MATCH PREDICTIONS & RATING TARGETS:')
    print('-' * 80)
    
    for match in matches:
        round_name = match.get('round', 'Unknown Round')
        team1 = match.get('team1', [])
        team2 = match.get('team2', [])
        
        print(f'\\n{round_name}')
        print('-' * 50)
        print(f'Team 1: {team1[0]} & {team1[1]}')
        print(f'Team 2: {team2[0]} & {team2[1]}')
        
        # Get player ratings
        team1_ratings = []
        team2_ratings = []
        
        for player in team1:
            if player in player_db:
                team1_ratings.append(player_db[player]['rating'])
            else:
                print(f'  ⚠️  Unknown player: {player}')
                team1_ratings.append(3.0)  # Default rating
        
        for player in team2:
            if player in player_db:
                team2_ratings.append(player_db[player]['rating'])
            else:
                print(f'  ⚠️  Unknown player: {player}')
                team2_ratings.append(3.0)  # Default rating
        
        # Calculate average ratings
        team1_avg = sum(team1_ratings) / len(team1_ratings)
        team2_avg = sum(team2_ratings) / len(team2_ratings)
        
        print(f'  Team 1 Avg Rating: {team1_avg:.3f}')
        print(f'  Team 2 Avg Rating: {team2_avg:.3f}')
        
        # Get expected scores from DUPR API
        try:
            team1_numeric = [numeric_ids.get(p, 0) for p in team1]
            team2_numeric = [numeric_ids.get(p, 0) for p in team2]
            
            teams = [
                {'player1Id': team1_numeric[0], 'player2Id': team1_numeric[1]},
                {'player1Id': team2_numeric[0], 'player2Id': team2_numeric[1]}
            ]
            
            rc, results = dupr.get_expected_score(teams)
            
            if rc == 200 and results:
                teams_result = results.get('teams', [])
                if len(teams_result) >= 2:
                    team1_score = teams_result[0].get('score', 'N/A')
                    team2_score = teams_result[1].get('score', 'N/A')
                    
                    print(f'\\n📊 Expected Scores:')
                    print(f'  {team1[0]} & {team1[1]}: {team1_score}')
                    print(f'  {team2[0]} & {team2[1]}: {team2_score}')
                    
                    # Determine winner and rating implications
                    if isinstance(team1_score, (int, float)) and isinstance(team2_score, (int, float)):
                        if team1_score > team2_score:
                            winner = f'{team1[0]} & {team1[1]}'
                            margin = team1_score - team2_score
                            print(f'🏆 Predicted Winner: {winner}')
                            print(f'   Margin: +{margin:.1f} points')
                            
                            # Rating improvement analysis
                            if team1_avg > team2_avg:
                                print(f'   💡 Team 1 favored - win by {margin:.1f}+ for max rating gain')
                            else:
                                print(f'   💡 Team 1 underdog - any win = big rating boost!')
                                
                        elif team2_score > team1_score:
                            winner = f'{team2[0]} & {team2[1]}'
                            margin = team2_score - team1_score
                            print(f'🏆 Predicted Winner: {winner}')
                            print(f'   Margin: +{margin:.1f} points')
                            
                            # Rating improvement analysis
                            if team2_avg > team1_avg:
                                print(f'   💡 Team 2 favored - win by {margin:.1f}+ for max rating gain')
                            else:
                                print(f'   💡 Team 2 underdog - any win = big rating boost!')
                        else:
                            print(f'🤝 Predicted: Tie')
                            print(f'   💡 Very competitive - any win = significant rating boost!')
                else:
                    print('❌ Invalid response format')
            else:
                print(f'❌ Failed to get expected score (status: {rc})')
                
        except Exception as e:
            print(f'❌ Error getting expected score: {e}')
            # Fallback to rating-based prediction
            rating_diff = abs(team1_avg - team2_avg)
            if rating_diff < 0.1:
                print(f'📊 Rating-based prediction: Very close match (diff: {rating_diff:.3f})')
            elif team1_avg > team2_avg:
                print(f'📊 Rating-based prediction: {team1[0]} & {team1[1]} favored')
            else:
                print(f'📊 Rating-based prediction: {team2[0]} & {team2[1]} favored')

@click.command()
def create_match_template():
    """Create a template file for match analysis"""
    import json
    
    template = {
        "matches": [
            {
                "round": "Round 1",
                "team1": ["Player1", "Player2"],
                "team2": ["Player3", "Player4"]
            },
            {
                "round": "Round 2", 
                "team1": ["Player5", "Player6"],
                "team2": ["Player7", "Player8"]
            }
        ]
    }
    
    with open('match_template.json', 'w') as f:
        json.dump(template, f, indent=2)
    
    print('📝 Created match_template.json')
    print('Edit this file with your actual matches and run:')
    print('python3 duprly.py analyze-matches match_template.json')

