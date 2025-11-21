#!/usr/bin/env python3
"""
DUPRLY MCP Server
Exposes DUPR (Dynamic Universal Pickleball Rating) functionality via MCP
"""

import os
import sys
import json
from typing import Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError as e:
    print(f"Error: mcp package not installed. Install with: pip install mcp", file=sys.stderr)
    print(f"Import error: {e}", file=sys.stderr)
    sys.exit(1)

from dupr_client import DuprClient
from dupr_db import open_db, Player, Match, Rating, MatchDetail
from sqlalchemy import select, func
from sqlalchemy.orm import Session

# Initialize DUPR client and database
dupr = DuprClient()
eng = open_db()

# Create MCP server
server = Server("duprly")


def ensure_auth():
    """Ensure we're authenticated with DUPR"""
    username = os.getenv("DUPR_USERNAME")
    password = os.getenv("DUPR_PASSWORD")
    if not username or not password:
        raise ValueError("DUPR_USERNAME and DUPR_PASSWORD must be set in .env file")
    dupr.auth_user(username, password)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    return [
        Tool(
            name="search_players",
            description="Search for DUPR players by name. Returns player information including ratings, location, and DUPR ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Player name to search for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 25)",
                        "default": 25
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_player",
            description="Get detailed information about a specific player by DUPR ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_id": {
                        "type": "string",
                        "description": "DUPR player ID (numeric or alphanumeric)"
                    }
                },
                "required": ["player_id"]
            }
        ),
        Tool(
            name="get_player_matches",
            description="Get match history for a specific player",
            inputSchema={
                "type": "object",
                "properties": {
                    "dupr_id": {
                        "type": "string",
                        "description": "DUPR player ID"
                    }
                },
                "required": ["dupr_id"]
            }
        ),
        Tool(
            name="get_expected_score",
            description="Get expected scores for a doubles match between two teams. Useful for predicting match outcomes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player1_id": {
                        "type": "integer",
                        "description": "Numeric DUPR ID for player 1 on team 1"
                    },
                    "player2_id": {
                        "type": "integer",
                        "description": "Numeric DUPR ID for player 2 on team 1"
                    },
                    "player3_id": {
                        "type": "integer",
                        "description": "Numeric DUPR ID for player 1 on team 2"
                    },
                    "player4_id": {
                        "type": "integer",
                        "description": "Numeric DUPR ID for player 2 on team 2"
                    }
                },
                "required": ["player1_id", "player2_id", "player3_id", "player4_id"]
            }
        ),
        Tool(
            name="get_club_members",
            description="Get all members from your DUPR club",
            inputSchema={
                "type": "object",
                "properties": {
                    "club_id": {
                        "type": "string",
                        "description": "DUPR club ID (optional, uses DUPR_CLUB_ID from .env if not provided)"
                    }
                }
            }
        ),
        Tool(
            name="get_database_stats",
            description="Get statistics about the local DUPR database (number of players, matches, etc.)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="query_players",
            description="Query players from the local database by name or DUPR ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (name or DUPR ID)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_player_rating_history",
            description="Get a player's rating history from the local database",
            inputSchema={
                "type": "object",
                "properties": {
                    "dupr_id": {
                        "type": "string",
                        "description": "DUPR player ID"
                    }
                },
                "required": ["dupr_id"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "search_players":
            ensure_auth()
            query = arguments.get("query")
            limit = arguments.get("limit", 25)
            
            rc, results = dupr.search_players(query, limit=limit)
            if rc == 200 and results:
                hits = results.get("hits", [])
                total = results.get("total", 0)
                
                output = f"Found {total} players matching '{query}':\n\n"
                for i, player in enumerate(hits[:limit], 1):
                    name = player.get("fullName", "Unknown")
                    dupr_id = player.get("duprId", "Unknown")
                    age = player.get("age", "Unknown")
                    location = player.get("shortAddress", "Unknown")
                    
                    ratings = player.get("ratings", {})
                    doubles = ratings.get("doubles", "NR")
                    singles = ratings.get("singles", "NR")
                    
                    output += f"{i}. {name}\n"
                    output += f"   DUPR ID: {dupr_id}\n"
                    output += f"   Age: {age}, Location: {location}\n"
                    output += f"   Doubles: {doubles}, Singles: {singles}\n\n"
                
                return [TextContent(type="text", text=output)]
            else:
                return [TextContent(type="text", text=f"Search failed (status: {rc})")]
        
        elif name == "get_player":
            ensure_auth()
            player_id = arguments.get("player_id")
            
            rc, player_data = dupr.get_player(player_id)
            if rc == 200 and player_data:
                output = json.dumps(player_data, indent=2)
                return [TextContent(type="text", text=output)]
            else:
                return [TextContent(type="text", text=f"Failed to get player (status: {rc})")]
        
        elif name == "get_player_matches":
            ensure_auth()
            dupr_id = arguments.get("dupr_id")
            
            rc, matches = dupr.get_member_match_history_p(dupr_id)
            if rc == 200:
                output = f"Found {len(matches)} matches for player {dupr_id}:\n\n"
                for i, match in enumerate(matches[:10], 1):  # Limit to 10 for display
                    event_date = match.get("eventDate", "Unknown")
                    event_name = match.get("eventName", match.get("league", match.get("tournament", "Unknown")))
                    teams = match.get("teams", [])
                    
                    output += f"{i}. {event_name} ({event_date})\n"
                    for team in teams:
                        p1 = team.get("player1", {})
                        p2 = team.get("player2", {})
                        score = team.get("game1", "N/A")
                        winner = "🏆" if team.get("winner") else ""
                        p1_name = p1.get("fullName", "Unknown")
                        p2_name = p2.get("fullName", "") if p2 else ""
                        team_str = f"{p1_name}" + (f" & {p2_name}" if p2_name else "")
                        output += f"   {winner} {team_str}: {score}\n"
                    output += "\n"
                
                if len(matches) > 10:
                    output += f"... and {len(matches) - 10} more matches\n"
                
                return [TextContent(type="text", text=output)]
            else:
                return [TextContent(type="text", text=f"Failed to get matches (status: {rc})")]
        
        elif name == "get_expected_score":
            ensure_auth()
            player1_id = arguments.get("player1_id")
            player2_id = arguments.get("player2_id")
            player3_id = arguments.get("player3_id")
            player4_id = arguments.get("player4_id")
            
            teams = [
                {"player1Id": int(player1_id), "player2Id": int(player2_id)},
                {"player1Id": int(player3_id), "player2Id": int(player4_id)},
            ]
            
            rc, results = dupr.get_expected_score(teams)
            if rc == 200 and results:
                teams_result = results.get("teams", [])
                if len(teams_result) >= 2:
                    team1_score = teams_result[0].get("score", "N/A")
                    team2_score = teams_result[1].get("score", "N/A")
                    
                    output = f"Expected Scores:\n"
                    output += f"  Team 1 (Players {player1_id} & {player2_id}): {team1_score}\n"
                    output += f"  Team 2 (Players {player3_id} & {player4_id}): {team2_score}\n\n"
                    
                    if isinstance(team1_score, (int, float)) and isinstance(team2_score, (int, float)):
                        if team1_score > team2_score:
                            output += f"🏆 Predicted Winner: Team 1 (by {team1_score - team2_score:.1f} points)"
                        elif team2_score > team1_score:
                            output += f"🏆 Predicted Winner: Team 2 (by {team2_score - team1_score:.1f} points)"
                        else:
                            output += f"🤝 Predicted: Tie"
                    
                    return [TextContent(type="text", text=output)]
                else:
                    return [TextContent(type="text", text="Invalid response format")]
            else:
                return [TextContent(type="text", text=f"Failed to get expected score (status: {rc})")]
        
        elif name == "get_club_members":
            ensure_auth()
            club_id = arguments.get("club_id") or os.getenv("DUPR_CLUB_ID")
            if not club_id:
                return [TextContent(type="text", text="Error: club_id required or DUPR_CLUB_ID must be set in .env")]
            
            rc, members = dupr.get_members_by_club(club_id)
            if rc == 200:
                output = f"Found {len(members)} club members:\n\n"
                for i, member in enumerate(members[:50], 1):  # Limit to 50 for display
                    name = member.get("fullName", "Unknown")
                    dupr_id = member.get("duprId", member.get("id", "Unknown"))
                    ratings = member.get("ratings", {})
                    doubles = ratings.get("doubles", "NR")
                    singles = ratings.get("singles", "NR")
                    
                    output += f"{i}. {name} (ID: {dupr_id})\n"
                    output += f"   Doubles: {doubles}, Singles: {singles}\n\n"
                
                if len(members) > 50:
                    output += f"... and {len(members) - 50} more members\n"
                
                return [TextContent(type="text", text=output)]
            else:
                return [TextContent(type="text", text=f"Failed to get club members (status: {rc})")]
        
        elif name == "get_database_stats":
            with Session(eng) as sess:
                player_count = sess.scalar(select(func.count(Player.id)))
                match_count = sess.scalar(select(func.count(Match.id)))
                
                output = "DUPR Database Statistics:\n"
                output += f"  Players: {player_count}\n"
                output += f"  Matches: {match_count}\n"
                
                return [TextContent(type="text", text=output)]
        
        elif name == "query_players":
            query = arguments.get("query", "").lower()
            with Session(eng) as sess:
                from sqlalchemy import cast, String, or_
                # Search by name or DUPR ID
                # Try to match as integer first, then as string
                try:
                    query_int = int(query)
                    players = sess.scalars(
                        select(Player).where(
                            or_(
                                Player.full_name.ilike(f"%{query}%"),
                                Player.dupr_id == query_int
                            )
                        ).limit(20)
                    ).all()
                except ValueError:
                    # Not a number, search as string
                    players = sess.scalars(
                        select(Player).where(
                            Player.full_name.ilike(f"%{query}%")
                        ).limit(20)
                    ).all()
                
                if not players:
                    return [TextContent(type="text", text=f"No players found matching '{query}'")]
                
                output = f"Found {len(players)} players:\n\n"
                for player in players:
                    rating_str = str(player.rating) if player.rating else "No rating"
                    output += f"- {player.full_name} (DUPR ID: {player.dupr_id})\n"
                    output += f"  Rating: {rating_str}\n"
                    if player.email:
                        output += f"  Email: {player.email}\n"
                    output += "\n"
                
                return [TextContent(type="text", text=output)]
        
        elif name == "get_player_rating_history":
            dupr_id = arguments.get("dupr_id")
            with Session(eng) as sess:
                # Try to convert to int if possible, otherwise search as string
                try:
                    dupr_id_int = int(dupr_id)
                    player = sess.scalar(select(Player).where(Player.dupr_id == dupr_id_int))
                except ValueError:
                    # If not a number, search as string (cast to string for comparison)
                    from sqlalchemy import cast, String
                    player = sess.scalar(select(Player).where(cast(Player.dupr_id, String) == dupr_id))
                
                if not player:
                    return [TextContent(type="text", text=f"Player with DUPR ID {dupr_id} not found in database")]
                
                output = f"Player: {player.full_name} (DUPR ID: {player.dupr_id})\n\n"
                if player.rating:
                    output += "Current Ratings:\n"
                    output += f"  Doubles: {player.rating.doubles_rating()}\n"
                    output += f"  Singles: {player.rating.singles_rating()}\n"
                else:
                    output += "No rating data available\n"
                
                return [TextContent(type="text", text=output)]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

