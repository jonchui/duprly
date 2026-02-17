-- Postgres schema for duprly backend.
-- Requires pgvector for similarity search.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE players (
    player_id text PRIMARY KEY,
    display_name text,
    gender text,
    age integer,
    location text,
    doubles_rating numeric,
    singles_rating numeric,
    reliability integer,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX players_reliability_idx ON players (reliability);
CREATE INDEX players_doubles_rating_idx ON players (doubles_rating);

CREATE TABLE matches (
    match_id text PRIMARY KEY,
    played_at timestamptz NOT NULL,
    match_type text,
    score_for integer,
    score_against integer,
    winner_side smallint,
    metadata jsonb,
    ingested_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX matches_played_at_idx ON matches (played_at DESC);
CREATE INDEX matches_match_type_played_at_idx ON matches (match_type, played_at DESC);

CREATE TABLE match_participants (
    match_id text NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    player_id text NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    side smallint NOT NULL,
    position smallint,
    pre_doubles_rating numeric,
    pre_reliability integer,
    PRIMARY KEY (match_id, player_id)
);

CREATE INDEX match_participants_match_idx ON match_participants (match_id);
CREATE INDEX match_participants_player_idx ON match_participants (player_id);

CREATE TABLE club_memberships (
    club_id text NOT NULL,
    player_id text NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    role text NOT NULL,
    status text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (club_id, player_id)
);

CREATE INDEX club_memberships_club_status_idx ON club_memberships (club_id, status);
CREATE INDEX club_memberships_player_idx ON club_memberships (player_id);

CREATE TABLE crawl_state (
    player_id text PRIMARY KEY REFERENCES players(player_id) ON DELETE CASCADE,
    last_crawled_at timestamptz,
    cursor text,
    priority integer NOT NULL DEFAULT 0,
    error_count integer NOT NULL DEFAULT 0,
    next_retry_at timestamptz
);

CREATE TABLE match_features (
    match_id text PRIMARY KEY REFERENCES matches(match_id) ON DELETE CASCADE,
    feature_vector vector(10),
    avg_opponent_rating numeric,
    avg_opponent_reliability numeric,
    rating_diff_expected numeric,
    margin integer,
    upset_score numeric,
    is_blowout boolean,
    is_tournament boolean,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Use ivfflat or hnsw depending on pgvector version and data size.
CREATE INDEX match_features_vector_idx
    ON match_features USING hnsw (feature_vector vector_l2_ops);
