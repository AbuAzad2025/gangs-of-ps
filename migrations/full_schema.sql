--
-- PostgreSQL database dump
--

\restrict Qh9BYuCU0LAOH1PvAkskGRzcNThy07z1bj8i1SeSvVay7p36dLWjWtrNrzK5YEU

-- Dumped from database version 18.1
-- Dumped by pg_dump version 18.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: postgres
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO postgres;

--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: postgres
--

COMMENT ON SCHEMA public IS '';


--
-- Name: userrole; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.userrole AS ENUM (
    'GUEST',
    'USER',
    'SUBSCRIBER',
    'MODERATOR',
    'ADMIN',
    'SUPER_ADMIN',
    'DEVELOPER'
);


ALTER TYPE public.userrole OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: achievement; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.achievement (
    id integer NOT NULL,
    key character varying(64) NOT NULL,
    title character varying(128) NOT NULL,
    description character varying(255),
    points integer,
    created_at timestamp without time zone
);


ALTER TABLE public.achievement OWNER TO postgres;

--
-- Name: achievement_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.achievement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.achievement_id_seq OWNER TO postgres;

--
-- Name: achievement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.achievement_id_seq OWNED BY public.achievement.id;


--
-- Name: active_intel; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.active_intel (
    id integer NOT NULL,
    user_id integer NOT NULL,
    target_id integer NOT NULL,
    start_time timestamp without time zone NOT NULL,
    expires_at timestamp without time zone NOT NULL
);


ALTER TABLE public.active_intel OWNER TO postgres;

--
-- Name: active_intel_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.active_intel_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.active_intel_id_seq OWNER TO postgres;

--
-- Name: active_intel_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.active_intel_id_seq OWNED BY public.active_intel.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: announcement; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.announcement (
    id integer NOT NULL,
    title character varying(100) NOT NULL,
    content text NOT NULL,
    is_active boolean,
    created_at timestamp without time zone
);


ALTER TABLE public.announcement OWNER TO postgres;

--
-- Name: announcement_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.announcement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.announcement_id_seq OWNER TO postgres;

--
-- Name: announcement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.announcement_id_seq OWNED BY public.announcement.id;


--
-- Name: asset; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.asset (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    type character varying(50) NOT NULL,
    owner_id integer,
    gang_id integer,
    value integer,
    income integer,
    last_collected timestamp without time zone,
    image character varying(255),
    is_active boolean,
    maintenance_cost integer DEFAULT 0
);


ALTER TABLE public.asset OWNER TO postgres;

--
-- Name: asset_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.asset_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.asset_id_seq OWNER TO postgres;

--
-- Name: asset_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.asset_id_seq OWNED BY public.asset.id;


--
-- Name: auction; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auction (
    id integer NOT NULL,
    item_type character varying(20) NOT NULL,
    item_id character varying(50),
    seller_id integer,
    start_price bigint NOT NULL,
    current_price bigint NOT NULL,
    min_bid_increment bigint,
    start_time timestamp without time zone,
    end_time timestamp without time zone NOT NULL,
    status character varying(20),
    winner_id integer
);


ALTER TABLE public.auction OWNER TO postgres;

--
-- Name: auction_bid; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auction_bid (
    id integer NOT NULL,
    auction_id integer NOT NULL,
    bidder_id integer NOT NULL,
    amount bigint NOT NULL,
    "timestamp" timestamp without time zone,
    is_refunded boolean DEFAULT false
);


ALTER TABLE public.auction_bid OWNER TO postgres;

--
-- Name: auction_bid_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.auction_bid_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.auction_bid_id_seq OWNER TO postgres;

--
-- Name: auction_bid_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.auction_bid_id_seq OWNED BY public.auction_bid.id;


--
-- Name: auction_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.auction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.auction_id_seq OWNER TO postgres;

--
-- Name: auction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.auction_id_seq OWNED BY public.auction.id;


--
-- Name: bounty; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bounty (
    id integer NOT NULL,
    placer_id integer NOT NULL,
    target_id integer NOT NULL,
    amount integer NOT NULL,
    created_at timestamp without time zone,
    is_anonymous boolean
);


ALTER TABLE public.bounty OWNER TO postgres;

--
-- Name: bounty_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bounty_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bounty_id_seq OWNER TO postgres;

--
-- Name: bounty_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bounty_id_seq OWNED BY public.bounty.id;


--
-- Name: combat_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.combat_log (
    id integer NOT NULL,
    attacker_id integer NOT NULL,
    defender_id integer NOT NULL,
    winner_id integer NOT NULL,
    money_stolen integer,
    exp_gain integer,
    is_attacker_anonymous boolean,
    "timestamp" timestamp without time zone
);


ALTER TABLE public.combat_log OWNER TO postgres;

--
-- Name: combat_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.combat_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.combat_log_id_seq OWNER TO postgres;

--
-- Name: combat_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.combat_log_id_seq OWNED BY public.combat_log.id;


--
-- Name: config_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.config_log (
    id integer NOT NULL,
    admin_id integer NOT NULL,
    key character varying(100) NOT NULL,
    old_value character varying(255),
    new_value character varying(255),
    reason character varying(255),
    "timestamp" timestamp without time zone
);


ALTER TABLE public.config_log OWNER TO postgres;

--
-- Name: config_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.config_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.config_log_id_seq OWNER TO postgres;

--
-- Name: config_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.config_log_id_seq OWNED BY public.config_log.id;


--
-- Name: crime; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.crime (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description character varying(255),
    energy_cost integer,
    money_reward_min integer,
    money_reward_max integer,
    exp_reward integer,
    min_level integer,
    cooldown integer,
    image character varying(100),
    is_active boolean,
    reward_type character varying(20),
    reward_item_id integer,
    min_strength integer,
    min_agility integer,
    min_intelligence integer
);


ALTER TABLE public.crime OWNER TO postgres;

--
-- Name: crime_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.crime_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.crime_id_seq OWNER TO postgres;

--
-- Name: crime_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.crime_id_seq OWNED BY public.crime.id;


--
-- Name: crime_lobby; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.crime_lobby (
    id integer NOT NULL,
    crime_id integer NOT NULL,
    leader_id integer NOT NULL,
    status character varying(20),
    created_at timestamp without time zone,
    started_at timestamp without time zone
);


ALTER TABLE public.crime_lobby OWNER TO postgres;

--
-- Name: crime_lobby_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.crime_lobby_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.crime_lobby_id_seq OWNER TO postgres;

--
-- Name: crime_lobby_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.crime_lobby_id_seq OWNED BY public.crime_lobby.id;


--
-- Name: daily_task; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.daily_task (
    id integer NOT NULL,
    description character varying(255) NOT NULL,
    target_type character varying(50) NOT NULL,
    target_count integer,
    reward_money integer,
    reward_exp integer,
    min_level integer,
    is_active boolean
);


ALTER TABLE public.daily_task OWNER TO postgres;

--
-- Name: daily_task_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.daily_task_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.daily_task_id_seq OWNER TO postgres;

--
-- Name: daily_task_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.daily_task_id_seq OWNED BY public.daily_task.id;


--
-- Name: economy_snapshot; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.economy_snapshot (
    id integer NOT NULL,
    date date,
    total_money bigint,
    total_bank bigint,
    avg_wealth bigint,
    top_1_percent_share double precision,
    active_users_24h integer,
    created_at timestamp without time zone
);


ALTER TABLE public.economy_snapshot OWNER TO postgres;

--
-- Name: economy_snapshot_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.economy_snapshot_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.economy_snapshot_id_seq OWNER TO postgres;

--
-- Name: economy_snapshot_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.economy_snapshot_id_seq OWNED BY public.economy_snapshot.id;


--
-- Name: elite_title_seat; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.elite_title_seat (
    id integer NOT NULL,
    title_key character varying(32) NOT NULL,
    seat_index integer NOT NULL,
    user_id integer,
    reserved_until timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.elite_title_seat OWNER TO postgres;

--
-- Name: elite_title_seat_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.elite_title_seat_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.elite_title_seat_id_seq OWNER TO postgres;

--
-- Name: elite_title_seat_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.elite_title_seat_id_seq OWNED BY public.elite_title_seat.id;


--
-- Name: factory_job; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.factory_job (
    id integer NOT NULL,
    user_id integer NOT NULL,
    job_type character varying(32) NOT NULL,
    metal_used integer DEFAULT 0,
    diamonds_used integer DEFAULT 0,
    output_amount integer DEFAULT 0,
    status character varying(16) DEFAULT 'running'::character varying,
    started_at timestamp without time zone DEFAULT now(),
    ends_at timestamp without time zone NOT NULL,
    claimed_at timestamp without time zone
);


ALTER TABLE public.factory_job OWNER TO postgres;

--
-- Name: factory_job_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.factory_job_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.factory_job_id_seq OWNER TO postgres;

--
-- Name: factory_job_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.factory_job_id_seq OWNED BY public.factory_job.id;


--
-- Name: farm_job; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.farm_job (
    id integer NOT NULL,
    user_id integer NOT NULL,
    farm_type character varying(32) NOT NULL,
    output_item_id integer,
    output_amount integer DEFAULT 0,
    diamonds_used integer DEFAULT 0,
    status character varying(16) DEFAULT 'running'::character varying,
    started_at timestamp without time zone DEFAULT now(),
    ends_at timestamp without time zone NOT NULL,
    claimed_at timestamp without time zone
);


ALTER TABLE public.farm_job OWNER TO postgres;

--
-- Name: farm_job_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.farm_job_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.farm_job_id_seq OWNER TO postgres;

--
-- Name: farm_job_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.farm_job_id_seq OWNED BY public.farm_job.id;


--
-- Name: farm_supply_contract; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.farm_supply_contract (
    id integer NOT NULL,
    user_id integer NOT NULL,
    location_id integer NOT NULL,
    bonus_percent double precision DEFAULT 0.1,
    status character varying(16) DEFAULT 'active'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    ends_at timestamp without time zone NOT NULL
);


ALTER TABLE public.farm_supply_contract OWNER TO postgres;

--
-- Name: farm_supply_contract_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.farm_supply_contract_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.farm_supply_contract_id_seq OWNER TO postgres;

--
-- Name: farm_supply_contract_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.farm_supply_contract_id_seq OWNED BY public.farm_supply_contract.id;


--
-- Name: forum_category; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.forum_category (
    id integer NOT NULL,
    title character varying(100) NOT NULL,
    description character varying(255),
    "order" integer,
    min_rank integer,
    created_at timestamp without time zone
);


ALTER TABLE public.forum_category OWNER TO postgres;

--
-- Name: forum_category_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.forum_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.forum_category_id_seq OWNER TO postgres;

--
-- Name: forum_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.forum_category_id_seq OWNED BY public.forum_category.id;


--
-- Name: forum_post; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.forum_post (
    id integer NOT NULL,
    topic_id integer NOT NULL,
    user_id integer NOT NULL,
    content text NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.forum_post OWNER TO postgres;

--
-- Name: forum_post_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.forum_post_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.forum_post_id_seq OWNER TO postgres;

--
-- Name: forum_post_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.forum_post_id_seq OWNED BY public.forum_post.id;


--
-- Name: forum_topic; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.forum_topic (
    id integer NOT NULL,
    category_id integer NOT NULL,
    user_id integer NOT NULL,
    title character varying(100) NOT NULL,
    is_pinned boolean,
    is_locked boolean,
    views integer,
    created_at timestamp without time zone,
    last_post_at timestamp without time zone
);


ALTER TABLE public.forum_topic OWNER TO postgres;

--
-- Name: forum_topic_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.forum_topic_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.forum_topic_id_seq OWNER TO postgres;

--
-- Name: forum_topic_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.forum_topic_id_seq OWNED BY public.forum_topic.id;


--
-- Name: futures_position; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.futures_position (
    id integer NOT NULL,
    user_id integer NOT NULL,
    asset_id integer NOT NULL,
    position_type character varying(10) NOT NULL,
    entry_price double precision NOT NULL,
    margin_amount double precision NOT NULL,
    leverage integer,
    quantity double precision NOT NULL,
    liquidation_price double precision NOT NULL,
    is_open boolean,
    opened_at timestamp without time zone,
    closed_at timestamp without time zone
);


ALTER TABLE public.futures_position OWNER TO postgres;

--
-- Name: futures_position_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.futures_position_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.futures_position_id_seq OWNER TO postgres;

--
-- Name: futures_position_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.futures_position_id_seq OWNED BY public.futures_position.id;


--
-- Name: game_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.game_log (
    id integer NOT NULL,
    admin_id integer NOT NULL,
    action character varying(128) NOT NULL,
    target_id integer,
    details text,
    "timestamp" timestamp without time zone
);


ALTER TABLE public.game_log OWNER TO postgres;

--
-- Name: game_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.game_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.game_log_id_seq OWNER TO postgres;

--
-- Name: game_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.game_log_id_seq OWNED BY public.game_log.id;


--
-- Name: gang; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.gang (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    image character varying(255),
    leader_id integer NOT NULL,
    underboss_id integer,
    level integer,
    exp integer,
    money integer,
    bullets integer,
    max_members integer,
    min_level_req integer,
    recruitment_status character varying(20),
    allowed_countries character varying(255),
    last_organized_crime_at timestamp without time zone,
    created_at timestamp without time zone
);


ALTER TABLE public.gang OWNER TO postgres;

--
-- Name: gang_alliance; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.gang_alliance (
    id integer NOT NULL,
    gang1_id integer NOT NULL,
    gang2_id integer NOT NULL,
    status character varying(20),
    created_at timestamp without time zone
);


ALTER TABLE public.gang_alliance OWNER TO postgres;

--
-- Name: gang_alliance_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.gang_alliance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gang_alliance_id_seq OWNER TO postgres;

--
-- Name: gang_alliance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.gang_alliance_id_seq OWNED BY public.gang_alliance.id;


--
-- Name: gang_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.gang_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gang_id_seq OWNER TO postgres;

--
-- Name: gang_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.gang_id_seq OWNED BY public.gang.id;


--
-- Name: gang_invite; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.gang_invite (
    id integer NOT NULL,
    gang_id integer NOT NULL,
    user_id integer NOT NULL,
    status character varying(20),
    created_at timestamp without time zone
);


ALTER TABLE public.gang_invite OWNER TO postgres;

--
-- Name: gang_invite_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.gang_invite_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gang_invite_id_seq OWNER TO postgres;

--
-- Name: gang_invite_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.gang_invite_id_seq OWNED BY public.gang_invite.id;


--
-- Name: gang_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.gang_log (
    id integer NOT NULL,
    gang_id integer NOT NULL,
    user_id integer,
    action character varying(255) NOT NULL,
    "timestamp" timestamp without time zone
);


ALTER TABLE public.gang_log OWNER TO postgres;

--
-- Name: gang_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.gang_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gang_log_id_seq OWNER TO postgres;

--
-- Name: gang_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.gang_log_id_seq OWNED BY public.gang_log.id;


--
-- Name: gang_war; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.gang_war (
    id integer NOT NULL,
    gang1_id integer NOT NULL,
    gang2_id integer NOT NULL,
    score_gang1 integer,
    score_gang2 integer,
    start_time timestamp without time zone,
    end_time timestamp without time zone,
    status character varying(20),
    war_type character varying(50),
    winner_id integer
);


ALTER TABLE public.gang_war OWNER TO postgres;

--
-- Name: gang_war_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.gang_war_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gang_war_id_seq OWNER TO postgres;

--
-- Name: gang_war_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.gang_war_id_seq OWNED BY public.gang_war.id;


--
-- Name: heist_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.heist_history (
    id integer NOT NULL,
    crime_name character varying(100),
    leader_name character varying(64),
    participants_snapshot json,
    success boolean,
    money_earned integer,
    exp_earned integer,
    log_details text,
    created_at timestamp without time zone
);


ALTER TABLE public.heist_history OWNER TO postgres;

--
-- Name: heist_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.heist_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.heist_history_id_seq OWNER TO postgres;

--
-- Name: heist_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.heist_history_id_seq OWNED BY public.heist_history.id;


--
-- Name: hostess_chat_messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.hostess_chat_messages (
    id integer NOT NULL,
    hostess_id integer NOT NULL,
    user_id integer,
    role character varying(16) NOT NULL,
    content text NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.hostess_chat_messages OWNER TO postgres;

--
-- Name: hostess_chat_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.hostess_chat_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.hostess_chat_messages_id_seq OWNER TO postgres;

--
-- Name: hostess_chat_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.hostess_chat_messages_id_seq OWNED BY public.hostess_chat_messages.id;


--
-- Name: hostess_knowledge; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.hostess_knowledge (
    id integer NOT NULL,
    hostess_id integer,
    question text NOT NULL,
    answer text NOT NULL,
    category character varying(64),
    keywords text,
    language character varying(10),
    created_at timestamp without time zone
);


ALTER TABLE public.hostess_knowledge OWNER TO postgres;

--
-- Name: hostess_knowledge_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.hostess_knowledge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.hostess_knowledge_id_seq OWNER TO postgres;

--
-- Name: hostess_knowledge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.hostess_knowledge_id_seq OWNED BY public.hostess_knowledge.id;


--
-- Name: hostess_memories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.hostess_memories (
    id integer NOT NULL,
    hostess_id integer NOT NULL,
    user_id integer NOT NULL,
    key character varying(64) NOT NULL,
    value text NOT NULL,
    importance integer,
    source character varying(16),
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.hostess_memories OWNER TO postgres;

--
-- Name: hostess_memories_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.hostess_memories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.hostess_memories_id_seq OWNER TO postgres;

--
-- Name: hostess_memories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.hostess_memories_id_seq OWNED BY public.hostess_memories.id;


--
-- Name: hostesses; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.hostesses (
    id integer NOT NULL,
    name character varying(64) NOT NULL,
    role character varying(32) NOT NULL,
    price integer,
    image character varying(128),
    description text,
    dialogue_style character varying(32),
    intro_message character varying(256),
    buff_type character varying(32),
    buff_value double precision,
    system_prompt text,
    training_examples text,
    video character varying(128),
    video_prompt text,
    voice_config text,
    personality_config text,
    appearance_config text,
    knowledge_base text,
    is_avatar_active boolean,
    is_active boolean,
    level integer,
    exp integer,
    charm integer,
    intelligence integer,
    combat_skill integer,
    loyalty integer,
    special_move_cooldown timestamp without time zone,
    current_player_id integer,
    min_rank integer,
    is_public boolean,
    self_learning_enabled boolean DEFAULT true,
    memory_enabled boolean DEFAULT true,
    last_trained_at timestamp without time zone
);


ALTER TABLE public.hostesses OWNER TO postgres;

--
-- Name: hostesses_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.hostesses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.hostesses_id_seq OWNER TO postgres;

--
-- Name: hostesses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.hostesses_id_seq OWNED BY public.hostesses.id;


--
-- Name: investigation_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.investigation_log (
    id integer NOT NULL,
    investigator_id integer NOT NULL,
    target_id integer NOT NULL,
    success boolean,
    details text,
    "timestamp" timestamp without time zone
);


ALTER TABLE public.investigation_log OWNER TO postgres;

--
-- Name: investigation_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.investigation_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.investigation_log_id_seq OWNER TO postgres;

--
-- Name: investigation_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.investigation_log_id_seq OWNED BY public.investigation_log.id;


--
-- Name: item; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.item (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    type character varying(50) NOT NULL,
    cost integer,
    is_black_market boolean,
    image character varying(255),
    bonus_strength integer,
    bonus_defense integer,
    bonus_agility integer,
    ammo_needed integer,
    recover_energy integer,
    recover_health integer,
    recover_brave integer
);


ALTER TABLE public.item OWNER TO postgres;

--
-- Name: item_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.item_id_seq OWNER TO postgres;

--
-- Name: item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.item_id_seq OWNED BY public.item.id;


--
-- Name: learning_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.learning_logs (
    id integer NOT NULL,
    user_id integer,
    user_question text NOT NULL,
    ai_response text NOT NULL,
    was_helpful boolean,
    created_at timestamp without time zone
);


ALTER TABLE public.learning_logs OWNER TO postgres;

--
-- Name: learning_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.learning_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.learning_logs_id_seq OWNER TO postgres;

--
-- Name: learning_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.learning_logs_id_seq OWNED BY public.learning_logs.id;


--
-- Name: lobby_participant; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lobby_participant (
    id integer NOT NULL,
    lobby_id integer NOT NULL,
    user_id integer NOT NULL,
    role_name character varying(50),
    is_ready boolean,
    joined_at timestamp without time zone
);


ALTER TABLE public.lobby_participant OWNER TO postgres;

--
-- Name: lobby_participant_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.lobby_participant_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lobby_participant_id_seq OWNER TO postgres;

--
-- Name: lobby_participant_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.lobby_participant_id_seq OWNED BY public.lobby_participant.id;


--
-- Name: location; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.location (
    id integer NOT NULL,
    name character varying(64) NOT NULL,
    description character varying(255),
    cost integer,
    cooldown integer,
    image character varying(100),
    specialty character varying(50),
    specialty_value integer
);


ALTER TABLE public.location OWNER TO postgres;

--
-- Name: location_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.location_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.location_id_seq OWNER TO postgres;

--
-- Name: location_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.location_id_seq OWNED BY public.location.id;


--
-- Name: market_asset; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.market_asset (
    id integer NOT NULL,
    symbol character varying(10) NOT NULL,
    name character varying(100) NOT NULL,
    asset_type character varying(20),
    current_price double precision,
    price_change_24h double precision,
    high_24h double precision,
    low_24h double precision,
    volume_24h double precision,
    last_updated timestamp without time zone
);


ALTER TABLE public.market_asset OWNER TO postgres;

--
-- Name: market_asset_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.market_asset_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.market_asset_id_seq OWNER TO postgres;

--
-- Name: market_asset_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.market_asset_id_seq OWNED BY public.market_asset.id;


--
-- Name: message; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.message (
    id integer NOT NULL,
    sender_id integer NOT NULL,
    receiver_id integer NOT NULL,
    subject character varying(100) NOT NULL,
    body text NOT NULL,
    is_read boolean,
    deleted_by_sender boolean,
    deleted_by_receiver boolean,
    "timestamp" timestamp without time zone,
    delivery_time timestamp without time zone
);


ALTER TABLE public.message OWNER TO postgres;

--
-- Name: message_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.message_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.message_id_seq OWNER TO postgres;

--
-- Name: message_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.message_id_seq OWNED BY public.message.id;


--
-- Name: money_sink_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.money_sink_log (
    id integer NOT NULL,
    user_id integer NOT NULL,
    sink_type character varying(50) NOT NULL,
    amount integer NOT NULL,
    details character varying(255),
    "timestamp" timestamp without time zone
);


ALTER TABLE public.money_sink_log OWNER TO postgres;

--
-- Name: money_sink_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.money_sink_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.money_sink_log_id_seq OWNER TO postgres;

--
-- Name: money_sink_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.money_sink_log_id_seq OWNED BY public.money_sink_log.id;


--
-- Name: notification; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notification (
    id integer NOT NULL,
    user_id integer NOT NULL,
    title character varying(100) NOT NULL,
    message text NOT NULL,
    is_read boolean,
    type character varying(50),
    link character varying(255),
    created_at timestamp without time zone
);


ALTER TABLE public.notification OWNER TO postgres;

--
-- Name: notification_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.notification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notification_id_seq OWNER TO postgres;

--
-- Name: notification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.notification_id_seq OWNED BY public.notification.id;


--
-- Name: organized_crime; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.organized_crime (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description character varying(255),
    min_level integer,
    min_members integer,
    max_members integer,
    duration_minutes integer,
    cooldown_hours integer,
    energy_cost integer,
    is_active boolean,
    money_reward_min integer,
    money_reward_max integer,
    exp_reward integer,
    requirements text,
    image character varying(100),
    roles_config json,
    min_gang_level integer
);


ALTER TABLE public.organized_crime OWNER TO postgres;

--
-- Name: organized_crime_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.organized_crime_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.organized_crime_id_seq OWNER TO postgres;

--
-- Name: organized_crime_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.organized_crime_id_seq OWNED BY public.organized_crime.id;


--
-- Name: payment_transaction; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.payment_transaction (
    id integer NOT NULL,
    user_id integer NOT NULL,
    amount_usd double precision NOT NULL,
    diamonds_amount integer NOT NULL,
    transaction_id character varying(100) NOT NULL,
    status character varying(20),
    payment_method character varying(50),
    payment_proof text,
    is_verified boolean,
    created_at timestamp without time zone
);


ALTER TABLE public.payment_transaction OWNER TO postgres;

--
-- Name: payment_transaction_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.payment_transaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.payment_transaction_id_seq OWNER TO postgres;

--
-- Name: payment_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.payment_transaction_id_seq OWNED BY public.payment_transaction.id;


--
-- Name: race; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.race (
    id integer NOT NULL,
    creator_id integer NOT NULL,
    status character varying(20),
    bet_amount integer NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.race OWNER TO postgres;

--
-- Name: race_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.race_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.race_id_seq OWNER TO postgres;

--
-- Name: race_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.race_id_seq OWNED BY public.race.id;


--
-- Name: race_participant; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.race_participant (
    id integer NOT NULL,
    race_id integer NOT NULL,
    user_id integer NOT NULL,
    user_vehicle_id integer NOT NULL,
    score double precision,
    rank integer,
    reward integer
);


ALTER TABLE public.race_participant OWNER TO postgres;

--
-- Name: race_participant_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.race_participant_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.race_participant_id_seq OWNER TO postgres;

--
-- Name: race_participant_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.race_participant_id_seq OWNED BY public.race_participant.id;


--
-- Name: referral; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.referral (
    id integer NOT NULL,
    referrer_id integer NOT NULL,
    referred_id integer NOT NULL,
    status character varying(20),
    created_at timestamp without time zone
);


ALTER TABLE public.referral OWNER TO postgres;

--
-- Name: referral_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.referral_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.referral_id_seq OWNER TO postgres;

--
-- Name: referral_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.referral_id_seq OWNED BY public.referral.id;


--
-- Name: resurrection_request; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.resurrection_request (
    id integer NOT NULL,
    user_id integer NOT NULL,
    status character varying(20),
    created_at timestamp without time zone,
    admin_note character varying(255)
);


ALTER TABLE public.resurrection_request OWNER TO postgres;

--
-- Name: resurrection_request_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.resurrection_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.resurrection_request_id_seq OWNER TO postgres;

--
-- Name: resurrection_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.resurrection_request_id_seq OWNED BY public.resurrection_request.id;


--
-- Name: security_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.security_log (
    id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    ip_address character varying(50),
    details text,
    "timestamp" timestamp without time zone
);


ALTER TABLE public.security_log OWNER TO postgres;

--
-- Name: security_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.security_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.security_log_id_seq OWNER TO postgres;

--
-- Name: security_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.security_log_id_seq OWNED BY public.security_log.id;


--
-- Name: spot_order; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.spot_order (
    id integer NOT NULL,
    user_id integer NOT NULL,
    asset_id integer NOT NULL,
    order_type character varying(10) NOT NULL,
    price double precision NOT NULL,
    quantity double precision NOT NULL,
    filled_quantity double precision,
    status character varying(20),
    created_at timestamp without time zone
);


ALTER TABLE public.spot_order OWNER TO postgres;

--
-- Name: spot_order_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.spot_order_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.spot_order_id_seq OWNER TO postgres;

--
-- Name: spot_order_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.spot_order_id_seq OWNED BY public.spot_order.id;


--
-- Name: system_config; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.system_config (
    id integer NOT NULL,
    key character varying(50) NOT NULL,
    value text,
    description character varying(255)
);


ALTER TABLE public.system_config OWNER TO postgres;

--
-- Name: system_config_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.system_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.system_config_id_seq OWNER TO postgres;

--
-- Name: system_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.system_config_id_seq OWNED BY public.system_config.id;


--
-- Name: user; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    username character varying(64) NOT NULL,
    password_hash character varying(256),
    role public.userrole,
    avatar character varying(100),
    country character varying(2),
    email character varying(120),
    is_verified boolean,
    verified_on timestamp without time zone,
    level integer,
    exp bigint,
    money bigint,
    bullets bigint,
    diamonds bigint,
    energy bigint,
    max_energy bigint,
    health integer,
    max_health integer,
    brave integer,
    max_brave integer,
    strength integer,
    defense integer,
    agility integer,
    intelligence integer,
    driving_skill integer,
    bank_balance bigint,
    jail_until timestamp without time zone,
    hospital_until timestamp without time zone,
    gym_until timestamp without time zone,
    is_safe_house_active boolean,
    safe_house_until timestamp without time zone,
    is_disguised boolean,
    disguise_until timestamp without time zone,
    casino_luck_until timestamp without time zone,
    active_hostess_id integer,
    is_ghost_mode boolean,
    banned_until timestamp without time zone,
    ban_reason character varying(255),
    gang_id integer,
    location_id integer,
    created_at timestamp without time zone,
    last_daily_reward timestamp without time zone,
    last_chase timestamp without time zone,
    crime_cooldown_until timestamp without time zone,
    organized_crime_cooldown_until timestamp without time zone,
    last_crime timestamp without time zone,
    last_travel timestamp without time zone,
    last_gym_training timestamp without time zone,
    last_attack timestamp without time zone,
    is_admin_protected boolean DEFAULT false,
    heat_points integer DEFAULT 0,
    heat_updated_at timestamp without time zone,
    daily_streak integer DEFAULT 0,
    is_suspicious boolean DEFAULT false,
    version integer DEFAULT 0 NOT NULL,
    daily_money_earned bigint DEFAULT 0,
    daily_money_date date DEFAULT CURRENT_DATE,
    gym_activity character varying(512),
    daily_bullets_purchased integer DEFAULT 0
);


ALTER TABLE public."user" OWNER TO postgres;

--
-- Name: user_achievement; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_achievement (
    id integer NOT NULL,
    user_id integer NOT NULL,
    achievement_id integer NOT NULL,
    unlocked_at timestamp without time zone
);


ALTER TABLE public.user_achievement OWNER TO postgres;

--
-- Name: user_achievement_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_achievement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_achievement_id_seq OWNER TO postgres;

--
-- Name: user_achievement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_achievement_id_seq OWNED BY public.user_achievement.id;


--
-- Name: user_crime_cooldown; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_crime_cooldown (
    id integer NOT NULL,
    user_id integer NOT NULL,
    crime_id integer NOT NULL,
    cooldown_until timestamp without time zone NOT NULL
);


ALTER TABLE public.user_crime_cooldown OWNER TO postgres;

--
-- Name: user_crime_cooldown_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_crime_cooldown_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_crime_cooldown_id_seq OWNER TO postgres;

--
-- Name: user_crime_cooldown_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_crime_cooldown_id_seq OWNED BY public.user_crime_cooldown.id;


--
-- Name: user_daily_task; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_daily_task (
    id integer NOT NULL,
    user_id integer NOT NULL,
    task_id integer NOT NULL,
    progress integer,
    is_completed boolean,
    date date
);


ALTER TABLE public.user_daily_task OWNER TO postgres;

--
-- Name: user_daily_task_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_daily_task_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_daily_task_id_seq OWNER TO postgres;

--
-- Name: user_daily_task_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_daily_task_id_seq OWNED BY public.user_daily_task.id;


--
-- Name: user_facility; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_facility (
    id integer NOT NULL,
    user_id integer NOT NULL,
    facility_key character varying(32) NOT NULL,
    level integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    last_perk_at timestamp without time zone
);


ALTER TABLE public.user_facility OWNER TO postgres;

--
-- Name: user_facility_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_facility_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_facility_id_seq OWNER TO postgres;

--
-- Name: user_facility_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_facility_id_seq OWNED BY public.user_facility.id;


--
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_id_seq OWNER TO postgres;

--
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- Name: user_investment; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_investment (
    id integer NOT NULL,
    user_id integer NOT NULL,
    asset_id integer NOT NULL,
    quantity double precision,
    average_buy_price double precision
);


ALTER TABLE public.user_investment OWNER TO postgres;

--
-- Name: user_investment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_investment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_investment_id_seq OWNER TO postgres;

--
-- Name: user_investment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_investment_id_seq OWNED BY public.user_investment.id;


--
-- Name: user_item; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_item (
    id integer NOT NULL,
    user_id integer NOT NULL,
    item_id integer NOT NULL,
    quantity integer,
    is_equipped boolean,
    condition integer
);


ALTER TABLE public.user_item OWNER TO postgres;

--
-- Name: user_item_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_item_id_seq OWNER TO postgres;

--
-- Name: user_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_item_id_seq OWNED BY public.user_item.id;


--
-- Name: user_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_log (
    id integer NOT NULL,
    user_id integer NOT NULL,
    action character varying(50) NOT NULL,
    details text,
    result character varying(20),
    ip_address character varying(45),
    user_agent character varying(255),
    "timestamp" timestamp without time zone,
    before_state json,
    after_state json
);


ALTER TABLE public.user_log OWNER TO postgres;

--
-- Name: user_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_log_id_seq OWNER TO postgres;

--
-- Name: user_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_log_id_seq OWNED BY public.user_log.id;


--
-- Name: user_progress; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_progress (
    id integer NOT NULL,
    user_id integer NOT NULL,
    rank_points integer
);


ALTER TABLE public.user_progress OWNER TO postgres;

--
-- Name: user_progress_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_progress_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_progress_id_seq OWNER TO postgres;

--
-- Name: user_progress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_progress_id_seq OWNED BY public.user_progress.id;


--
-- Name: user_rank; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_rank (
    id integer NOT NULL,
    name character varying(64) NOT NULL,
    min_level integer,
    resurrection_cost double precision
);


ALTER TABLE public.user_rank OWNER TO postgres;

--
-- Name: user_rank_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_rank_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_rank_id_seq OWNER TO postgres;

--
-- Name: user_rank_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_rank_id_seq OWNED BY public.user_rank.id;


--
-- Name: user_vehicle; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_vehicle (
    id integer NOT NULL,
    user_id integer NOT NULL,
    vehicle_id integer NOT NULL,
    is_active boolean,
    condition integer,
    engine_level integer,
    tires_level integer,
    armor_level integer,
    repair_until timestamp without time zone
);


ALTER TABLE public.user_vehicle OWNER TO postgres;

--
-- Name: user_vehicle_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_vehicle_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_vehicle_id_seq OWNER TO postgres;

--
-- Name: user_vehicle_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_vehicle_id_seq OWNED BY public.user_vehicle.id;


--
-- Name: vehicle; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vehicle (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    type character varying(50) NOT NULL,
    description character varying(255),
    price integer NOT NULL,
    speed integer,
    defense integer,
    risk integer,
    image character varying(100),
    is_active boolean
);


ALTER TABLE public.vehicle OWNER TO postgres;

--
-- Name: vehicle_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.vehicle_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.vehicle_id_seq OWNER TO postgres;

--
-- Name: vehicle_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.vehicle_id_seq OWNED BY public.vehicle.id;


--
-- Name: video_scenarios; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.video_scenarios (
    id integer NOT NULL,
    title character varying(128) NOT NULL,
    description text,
    script_json text NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.video_scenarios OWNER TO postgres;

--
-- Name: video_scenarios_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.video_scenarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.video_scenarios_id_seq OWNER TO postgres;

--
-- Name: video_scenarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.video_scenarios_id_seq OWNED BY public.video_scenarios.id;


--
-- Name: weekly_winner; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.weekly_winner (
    id integer NOT NULL,
    user_id integer NOT NULL,
    week_number integer NOT NULL,
    year integer NOT NULL,
    amount_won integer,
    created_at timestamp without time zone
);


ALTER TABLE public.weekly_winner OWNER TO postgres;

--
-- Name: weekly_winner_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.weekly_winner_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.weekly_winner_id_seq OWNER TO postgres;

--
-- Name: weekly_winner_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.weekly_winner_id_seq OWNED BY public.weekly_winner.id;


--
-- Name: achievement id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.achievement ALTER COLUMN id SET DEFAULT nextval('public.achievement_id_seq'::regclass);


--
-- Name: active_intel id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.active_intel ALTER COLUMN id SET DEFAULT nextval('public.active_intel_id_seq'::regclass);


--
-- Name: announcement id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcement ALTER COLUMN id SET DEFAULT nextval('public.announcement_id_seq'::regclass);


--
-- Name: asset id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset ALTER COLUMN id SET DEFAULT nextval('public.asset_id_seq'::regclass);


--
-- Name: auction id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auction ALTER COLUMN id SET DEFAULT nextval('public.auction_id_seq'::regclass);


--
-- Name: auction_bid id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auction_bid ALTER COLUMN id SET DEFAULT nextval('public.auction_bid_id_seq'::regclass);


--
-- Name: bounty id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bounty ALTER COLUMN id SET DEFAULT nextval('public.bounty_id_seq'::regclass);


--
-- Name: combat_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.combat_log ALTER COLUMN id SET DEFAULT nextval('public.combat_log_id_seq'::regclass);


--
-- Name: config_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.config_log ALTER COLUMN id SET DEFAULT nextval('public.config_log_id_seq'::regclass);


--
-- Name: crime id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crime ALTER COLUMN id SET DEFAULT nextval('public.crime_id_seq'::regclass);


--
-- Name: crime_lobby id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crime_lobby ALTER COLUMN id SET DEFAULT nextval('public.crime_lobby_id_seq'::regclass);


--
-- Name: daily_task id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_task ALTER COLUMN id SET DEFAULT nextval('public.daily_task_id_seq'::regclass);


--
-- Name: economy_snapshot id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.economy_snapshot ALTER COLUMN id SET DEFAULT nextval('public.economy_snapshot_id_seq'::regclass);


--
-- Name: elite_title_seat id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.elite_title_seat ALTER COLUMN id SET DEFAULT nextval('public.elite_title_seat_id_seq'::regclass);


--
-- Name: factory_job id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.factory_job ALTER COLUMN id SET DEFAULT nextval('public.factory_job_id_seq'::regclass);


--
-- Name: farm_job id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.farm_job ALTER COLUMN id SET DEFAULT nextval('public.farm_job_id_seq'::regclass);


--
-- Name: farm_supply_contract id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.farm_supply_contract ALTER COLUMN id SET DEFAULT nextval('public.farm_supply_contract_id_seq'::regclass);


--
-- Name: forum_category id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_category ALTER COLUMN id SET DEFAULT nextval('public.forum_category_id_seq'::regclass);


--
-- Name: forum_post id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_post ALTER COLUMN id SET DEFAULT nextval('public.forum_post_id_seq'::regclass);


--
-- Name: forum_topic id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_topic ALTER COLUMN id SET DEFAULT nextval('public.forum_topic_id_seq'::regclass);


--
-- Name: futures_position id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.futures_position ALTER COLUMN id SET DEFAULT nextval('public.futures_position_id_seq'::regclass);


--
-- Name: game_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.game_log ALTER COLUMN id SET DEFAULT nextval('public.game_log_id_seq'::regclass);


--
-- Name: gang id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang ALTER COLUMN id SET DEFAULT nextval('public.gang_id_seq'::regclass);


--
-- Name: gang_alliance id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_alliance ALTER COLUMN id SET DEFAULT nextval('public.gang_alliance_id_seq'::regclass);


--
-- Name: gang_invite id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_invite ALTER COLUMN id SET DEFAULT nextval('public.gang_invite_id_seq'::regclass);


--
-- Name: gang_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_log ALTER COLUMN id SET DEFAULT nextval('public.gang_log_id_seq'::regclass);


--
-- Name: gang_war id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_war ALTER COLUMN id SET DEFAULT nextval('public.gang_war_id_seq'::regclass);


--
-- Name: heist_history id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.heist_history ALTER COLUMN id SET DEFAULT nextval('public.heist_history_id_seq'::regclass);


--
-- Name: hostess_chat_messages id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostess_chat_messages ALTER COLUMN id SET DEFAULT nextval('public.hostess_chat_messages_id_seq'::regclass);


--
-- Name: hostess_knowledge id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostess_knowledge ALTER COLUMN id SET DEFAULT nextval('public.hostess_knowledge_id_seq'::regclass);


--
-- Name: hostess_memories id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostess_memories ALTER COLUMN id SET DEFAULT nextval('public.hostess_memories_id_seq'::regclass);


--
-- Name: hostesses id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostesses ALTER COLUMN id SET DEFAULT nextval('public.hostesses_id_seq'::regclass);


--
-- Name: investigation_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.investigation_log ALTER COLUMN id SET DEFAULT nextval('public.investigation_log_id_seq'::regclass);


--
-- Name: item id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.item ALTER COLUMN id SET DEFAULT nextval('public.item_id_seq'::regclass);


--
-- Name: learning_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.learning_logs ALTER COLUMN id SET DEFAULT nextval('public.learning_logs_id_seq'::regclass);


--
-- Name: lobby_participant id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobby_participant ALTER COLUMN id SET DEFAULT nextval('public.lobby_participant_id_seq'::regclass);


--
-- Name: location id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.location ALTER COLUMN id SET DEFAULT nextval('public.location_id_seq'::regclass);


--
-- Name: market_asset id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.market_asset ALTER COLUMN id SET DEFAULT nextval('public.market_asset_id_seq'::regclass);


--
-- Name: message id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.message ALTER COLUMN id SET DEFAULT nextval('public.message_id_seq'::regclass);


--
-- Name: money_sink_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.money_sink_log ALTER COLUMN id SET DEFAULT nextval('public.money_sink_log_id_seq'::regclass);


--
-- Name: notification id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification ALTER COLUMN id SET DEFAULT nextval('public.notification_id_seq'::regclass);


--
-- Name: organized_crime id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.organized_crime ALTER COLUMN id SET DEFAULT nextval('public.organized_crime_id_seq'::regclass);


--
-- Name: payment_transaction id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payment_transaction ALTER COLUMN id SET DEFAULT nextval('public.payment_transaction_id_seq'::regclass);


--
-- Name: race id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.race ALTER COLUMN id SET DEFAULT nextval('public.race_id_seq'::regclass);


--
-- Name: race_participant id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.race_participant ALTER COLUMN id SET DEFAULT nextval('public.race_participant_id_seq'::regclass);


--
-- Name: referral id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.referral ALTER COLUMN id SET DEFAULT nextval('public.referral_id_seq'::regclass);


--
-- Name: resurrection_request id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resurrection_request ALTER COLUMN id SET DEFAULT nextval('public.resurrection_request_id_seq'::regclass);


--
-- Name: security_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.security_log ALTER COLUMN id SET DEFAULT nextval('public.security_log_id_seq'::regclass);


--
-- Name: spot_order id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.spot_order ALTER COLUMN id SET DEFAULT nextval('public.spot_order_id_seq'::regclass);


--
-- Name: system_config id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.system_config ALTER COLUMN id SET DEFAULT nextval('public.system_config_id_seq'::regclass);


--
-- Name: user id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- Name: user_achievement id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_achievement ALTER COLUMN id SET DEFAULT nextval('public.user_achievement_id_seq'::regclass);


--
-- Name: user_crime_cooldown id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_crime_cooldown ALTER COLUMN id SET DEFAULT nextval('public.user_crime_cooldown_id_seq'::regclass);


--
-- Name: user_daily_task id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_daily_task ALTER COLUMN id SET DEFAULT nextval('public.user_daily_task_id_seq'::regclass);


--
-- Name: user_facility id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_facility ALTER COLUMN id SET DEFAULT nextval('public.user_facility_id_seq'::regclass);


--
-- Name: user_investment id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_investment ALTER COLUMN id SET DEFAULT nextval('public.user_investment_id_seq'::regclass);


--
-- Name: user_item id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_item ALTER COLUMN id SET DEFAULT nextval('public.user_item_id_seq'::regclass);


--
-- Name: user_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_log ALTER COLUMN id SET DEFAULT nextval('public.user_log_id_seq'::regclass);


--
-- Name: user_progress id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_progress ALTER COLUMN id SET DEFAULT nextval('public.user_progress_id_seq'::regclass);


--
-- Name: user_rank id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_rank ALTER COLUMN id SET DEFAULT nextval('public.user_rank_id_seq'::regclass);


--
-- Name: user_vehicle id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_vehicle ALTER COLUMN id SET DEFAULT nextval('public.user_vehicle_id_seq'::regclass);


--
-- Name: vehicle id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vehicle ALTER COLUMN id SET DEFAULT nextval('public.vehicle_id_seq'::regclass);


--
-- Name: video_scenarios id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.video_scenarios ALTER COLUMN id SET DEFAULT nextval('public.video_scenarios_id_seq'::regclass);


--
-- Name: weekly_winner id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.weekly_winner ALTER COLUMN id SET DEFAULT nextval('public.weekly_winner_id_seq'::regclass);


--
-- Name: achievement achievement_key_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.achievement
    ADD CONSTRAINT achievement_key_key UNIQUE (key);


--
-- Name: achievement achievement_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.achievement
    ADD CONSTRAINT achievement_pkey PRIMARY KEY (id);


--
-- Name: active_intel active_intel_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.active_intel
    ADD CONSTRAINT active_intel_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: announcement announcement_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcement
    ADD CONSTRAINT announcement_pkey PRIMARY KEY (id);


--
-- Name: asset asset_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset
    ADD CONSTRAINT asset_pkey PRIMARY KEY (id);


--
-- Name: auction_bid auction_bid_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auction_bid
    ADD CONSTRAINT auction_bid_pkey PRIMARY KEY (id);


--
-- Name: auction auction_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auction
    ADD CONSTRAINT auction_pkey PRIMARY KEY (id);


--
-- Name: bounty bounty_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bounty
    ADD CONSTRAINT bounty_pkey PRIMARY KEY (id);


--
-- Name: combat_log combat_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.combat_log
    ADD CONSTRAINT combat_log_pkey PRIMARY KEY (id);


--
-- Name: config_log config_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.config_log
    ADD CONSTRAINT config_log_pkey PRIMARY KEY (id);


--
-- Name: crime_lobby crime_lobby_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crime_lobby
    ADD CONSTRAINT crime_lobby_pkey PRIMARY KEY (id);


--
-- Name: crime crime_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crime
    ADD CONSTRAINT crime_name_key UNIQUE (name);


--
-- Name: crime crime_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crime
    ADD CONSTRAINT crime_pkey PRIMARY KEY (id);


--
-- Name: daily_task daily_task_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_task
    ADD CONSTRAINT daily_task_pkey PRIMARY KEY (id);


--
-- Name: economy_snapshot economy_snapshot_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.economy_snapshot
    ADD CONSTRAINT economy_snapshot_pkey PRIMARY KEY (id);


--
-- Name: elite_title_seat elite_title_seat_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.elite_title_seat
    ADD CONSTRAINT elite_title_seat_pkey PRIMARY KEY (id);


--
-- Name: factory_job factory_job_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.factory_job
    ADD CONSTRAINT factory_job_pkey PRIMARY KEY (id);


--
-- Name: farm_job farm_job_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.farm_job
    ADD CONSTRAINT farm_job_pkey PRIMARY KEY (id);


--
-- Name: farm_supply_contract farm_supply_contract_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.farm_supply_contract
    ADD CONSTRAINT farm_supply_contract_pkey PRIMARY KEY (id);


--
-- Name: forum_category forum_category_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_category
    ADD CONSTRAINT forum_category_pkey PRIMARY KEY (id);


--
-- Name: forum_post forum_post_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_post
    ADD CONSTRAINT forum_post_pkey PRIMARY KEY (id);


--
-- Name: forum_topic forum_topic_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_topic
    ADD CONSTRAINT forum_topic_pkey PRIMARY KEY (id);


--
-- Name: futures_position futures_position_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.futures_position
    ADD CONSTRAINT futures_position_pkey PRIMARY KEY (id);


--
-- Name: game_log game_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.game_log
    ADD CONSTRAINT game_log_pkey PRIMARY KEY (id);


--
-- Name: gang_alliance gang_alliance_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_alliance
    ADD CONSTRAINT gang_alliance_pkey PRIMARY KEY (id);


--
-- Name: gang_invite gang_invite_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_invite
    ADD CONSTRAINT gang_invite_pkey PRIMARY KEY (id);


--
-- Name: gang_log gang_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_log
    ADD CONSTRAINT gang_log_pkey PRIMARY KEY (id);


--
-- Name: gang gang_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang
    ADD CONSTRAINT gang_name_key UNIQUE (name);


--
-- Name: gang gang_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang
    ADD CONSTRAINT gang_pkey PRIMARY KEY (id);


--
-- Name: gang_war gang_war_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_war
    ADD CONSTRAINT gang_war_pkey PRIMARY KEY (id);


--
-- Name: heist_history heist_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.heist_history
    ADD CONSTRAINT heist_history_pkey PRIMARY KEY (id);


--
-- Name: hostess_chat_messages hostess_chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostess_chat_messages
    ADD CONSTRAINT hostess_chat_messages_pkey PRIMARY KEY (id);


--
-- Name: hostess_knowledge hostess_knowledge_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostess_knowledge
    ADD CONSTRAINT hostess_knowledge_pkey PRIMARY KEY (id);


--
-- Name: hostess_memories hostess_memories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostess_memories
    ADD CONSTRAINT hostess_memories_pkey PRIMARY KEY (id);


--
-- Name: hostesses hostesses_current_player_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostesses
    ADD CONSTRAINT hostesses_current_player_id_key UNIQUE (current_player_id);


--
-- Name: hostesses hostesses_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostesses
    ADD CONSTRAINT hostesses_pkey PRIMARY KEY (id);


--
-- Name: investigation_log investigation_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.investigation_log
    ADD CONSTRAINT investigation_log_pkey PRIMARY KEY (id);


--
-- Name: item item_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.item
    ADD CONSTRAINT item_pkey PRIMARY KEY (id);


--
-- Name: learning_logs learning_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.learning_logs
    ADD CONSTRAINT learning_logs_pkey PRIMARY KEY (id);


--
-- Name: lobby_participant lobby_participant_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobby_participant
    ADD CONSTRAINT lobby_participant_pkey PRIMARY KEY (id);


--
-- Name: location location_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.location
    ADD CONSTRAINT location_pkey PRIMARY KEY (id);


--
-- Name: market_asset market_asset_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.market_asset
    ADD CONSTRAINT market_asset_pkey PRIMARY KEY (id);


--
-- Name: market_asset market_asset_symbol_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.market_asset
    ADD CONSTRAINT market_asset_symbol_key UNIQUE (symbol);


--
-- Name: message message_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.message
    ADD CONSTRAINT message_pkey PRIMARY KEY (id);


--
-- Name: money_sink_log money_sink_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.money_sink_log
    ADD CONSTRAINT money_sink_log_pkey PRIMARY KEY (id);


--
-- Name: notification notification_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_pkey PRIMARY KEY (id);


--
-- Name: organized_crime organized_crime_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.organized_crime
    ADD CONSTRAINT organized_crime_name_key UNIQUE (name);


--
-- Name: organized_crime organized_crime_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.organized_crime
    ADD CONSTRAINT organized_crime_pkey PRIMARY KEY (id);


--
-- Name: payment_transaction payment_transaction_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payment_transaction
    ADD CONSTRAINT payment_transaction_pkey PRIMARY KEY (id);


--
-- Name: payment_transaction payment_transaction_transaction_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payment_transaction
    ADD CONSTRAINT payment_transaction_transaction_id_key UNIQUE (transaction_id);


--
-- Name: race_participant race_participant_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.race_participant
    ADD CONSTRAINT race_participant_pkey PRIMARY KEY (id);


--
-- Name: race race_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.race
    ADD CONSTRAINT race_pkey PRIMARY KEY (id);


--
-- Name: referral referral_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.referral
    ADD CONSTRAINT referral_pkey PRIMARY KEY (id);


--
-- Name: resurrection_request resurrection_request_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resurrection_request
    ADD CONSTRAINT resurrection_request_pkey PRIMARY KEY (id);


--
-- Name: security_log security_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.security_log
    ADD CONSTRAINT security_log_pkey PRIMARY KEY (id);


--
-- Name: spot_order spot_order_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.spot_order
    ADD CONSTRAINT spot_order_pkey PRIMARY KEY (id);


--
-- Name: system_config system_config_key_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.system_config
    ADD CONSTRAINT system_config_key_key UNIQUE (key);


--
-- Name: system_config system_config_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.system_config
    ADD CONSTRAINT system_config_pkey PRIMARY KEY (id);


--
-- Name: elite_title_seat uq_elite_title_seat_title_index; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.elite_title_seat
    ADD CONSTRAINT uq_elite_title_seat_title_index UNIQUE (title_key, seat_index);


--
-- Name: user_achievement user_achievement_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_achievement
    ADD CONSTRAINT user_achievement_pkey PRIMARY KEY (id);


--
-- Name: user_crime_cooldown user_crime_cooldown_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_crime_cooldown
    ADD CONSTRAINT user_crime_cooldown_pkey PRIMARY KEY (id);


--
-- Name: user_daily_task user_daily_task_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_daily_task
    ADD CONSTRAINT user_daily_task_pkey PRIMARY KEY (id);


--
-- Name: user user_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_email_key UNIQUE (email);


--
-- Name: user_facility user_facility_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_facility
    ADD CONSTRAINT user_facility_pkey PRIMARY KEY (id);


--
-- Name: user_investment user_investment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_investment
    ADD CONSTRAINT user_investment_pkey PRIMARY KEY (id);


--
-- Name: user_item user_item_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_item
    ADD CONSTRAINT user_item_pkey PRIMARY KEY (id);


--
-- Name: user_log user_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_log
    ADD CONSTRAINT user_log_pkey PRIMARY KEY (id);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: user_progress user_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_progress
    ADD CONSTRAINT user_progress_pkey PRIMARY KEY (id);


--
-- Name: user_rank user_rank_min_level_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_rank
    ADD CONSTRAINT user_rank_min_level_key UNIQUE (min_level);


--
-- Name: user_rank user_rank_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_rank
    ADD CONSTRAINT user_rank_pkey PRIMARY KEY (id);


--
-- Name: user user_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_username_key UNIQUE (username);


--
-- Name: user_vehicle user_vehicle_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_vehicle
    ADD CONSTRAINT user_vehicle_pkey PRIMARY KEY (id);


--
-- Name: vehicle vehicle_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vehicle
    ADD CONSTRAINT vehicle_pkey PRIMARY KEY (id);


--
-- Name: video_scenarios video_scenarios_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.video_scenarios
    ADD CONSTRAINT video_scenarios_pkey PRIMARY KEY (id);


--
-- Name: weekly_winner weekly_winner_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.weekly_winner
    ADD CONSTRAINT weekly_winner_pkey PRIMARY KEY (id);


--
-- Name: ix_auction_bid_auction_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_auction_bid_auction_id ON public.auction_bid USING btree (auction_id);


--
-- Name: ix_auction_bid_bidder_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_auction_bid_bidder_id ON public.auction_bid USING btree (bidder_id);


--
-- Name: ix_config_log_admin_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_config_log_admin_id ON public.config_log USING btree (admin_id);


--
-- Name: ix_config_log_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_config_log_timestamp ON public.config_log USING btree ("timestamp");


--
-- Name: ix_crime_lobby_leader_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_crime_lobby_leader_id ON public.crime_lobby USING btree (leader_id);


--
-- Name: ix_crime_lobby_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_crime_lobby_status ON public.crime_lobby USING btree (status);


--
-- Name: ix_economy_snapshot_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_economy_snapshot_date ON public.economy_snapshot USING btree (date);


--
-- Name: ix_elite_title_seat_title_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_elite_title_seat_title_key ON public.elite_title_seat USING btree (title_key);


--
-- Name: ix_elite_title_seat_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_elite_title_seat_user_id ON public.elite_title_seat USING btree (user_id);


--
-- Name: ix_factory_job_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_factory_job_user_id ON public.factory_job USING btree (user_id);


--
-- Name: ix_farm_job_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_farm_job_user_id ON public.farm_job USING btree (user_id);


--
-- Name: ix_farm_supply_contract_location_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_farm_supply_contract_location_id ON public.farm_supply_contract USING btree (location_id);


--
-- Name: ix_farm_supply_contract_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_farm_supply_contract_status ON public.farm_supply_contract USING btree (status);


--
-- Name: ix_farm_supply_contract_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_farm_supply_contract_user_id ON public.farm_supply_contract USING btree (user_id);


--
-- Name: ix_game_log_admin_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_game_log_admin_id ON public.game_log USING btree (admin_id);


--
-- Name: ix_game_log_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_game_log_timestamp ON public.game_log USING btree ("timestamp");


--
-- Name: ix_gang_invite_gang_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_gang_invite_gang_id ON public.gang_invite USING btree (gang_id);


--
-- Name: ix_gang_invite_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_gang_invite_user_id ON public.gang_invite USING btree (user_id);


--
-- Name: ix_gang_leader_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_gang_leader_id ON public.gang USING btree (leader_id);


--
-- Name: ix_hostess_chat_messages_hostess_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_hostess_chat_messages_hostess_id ON public.hostess_chat_messages USING btree (hostess_id);


--
-- Name: ix_hostess_chat_messages_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_hostess_chat_messages_user_id ON public.hostess_chat_messages USING btree (user_id);


--
-- Name: ix_hostess_knowledge_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_hostess_knowledge_category ON public.hostess_knowledge USING btree (category);


--
-- Name: ix_hostess_knowledge_language; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_hostess_knowledge_language ON public.hostess_knowledge USING btree (language);


--
-- Name: ix_hostess_memories_hostess_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_hostess_memories_hostess_id ON public.hostess_memories USING btree (hostess_id);


--
-- Name: ix_hostess_memories_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_hostess_memories_key ON public.hostess_memories USING btree (key);


--
-- Name: ix_hostess_memories_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_hostess_memories_user_id ON public.hostess_memories USING btree (user_id);


--
-- Name: ix_investigation_log_investigator_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_investigation_log_investigator_id ON public.investigation_log USING btree (investigator_id);


--
-- Name: ix_investigation_log_target_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_investigation_log_target_id ON public.investigation_log USING btree (target_id);


--
-- Name: ix_investigation_log_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_investigation_log_timestamp ON public.investigation_log USING btree ("timestamp");


--
-- Name: ix_lobby_participant_lobby_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_lobby_participant_lobby_id ON public.lobby_participant USING btree (lobby_id);


--
-- Name: ix_lobby_participant_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_lobby_participant_user_id ON public.lobby_participant USING btree (user_id);


--
-- Name: ix_money_sink_log_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_money_sink_log_timestamp ON public.money_sink_log USING btree ("timestamp");


--
-- Name: ix_money_sink_log_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_money_sink_log_user_id ON public.money_sink_log USING btree (user_id);


--
-- Name: ix_notification_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_notification_created_at ON public.notification USING btree (created_at);


--
-- Name: ix_notification_is_read; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_notification_is_read ON public.notification USING btree (is_read);


--
-- Name: ix_notification_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_notification_user_id ON public.notification USING btree (user_id);


--
-- Name: ix_user_achievement_achievement_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_achievement_achievement_id ON public.user_achievement USING btree (achievement_id);


--
-- Name: ix_user_achievement_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_achievement_user_id ON public.user_achievement USING btree (user_id);


--
-- Name: ix_user_facility_facility_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_facility_facility_key ON public.user_facility USING btree (facility_key);


--
-- Name: ix_user_facility_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_facility_user_id ON public.user_facility USING btree (user_id);


--
-- Name: ix_user_gang_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_gang_id ON public."user" USING btree (gang_id);


--
-- Name: ix_user_location_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_location_id ON public."user" USING btree (location_id);


--
-- Name: ix_user_log_action; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_log_action ON public.user_log USING btree (action);


--
-- Name: ix_user_log_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_log_timestamp ON public.user_log USING btree ("timestamp");


--
-- Name: ix_user_log_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_log_user_id ON public.user_log USING btree (user_id);


--
-- Name: active_intel active_intel_target_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.active_intel
    ADD CONSTRAINT active_intel_target_id_fkey FOREIGN KEY (target_id) REFERENCES public."user"(id);


--
-- Name: active_intel active_intel_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.active_intel
    ADD CONSTRAINT active_intel_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: asset asset_gang_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset
    ADD CONSTRAINT asset_gang_id_fkey FOREIGN KEY (gang_id) REFERENCES public.gang(id);


--
-- Name: asset asset_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset
    ADD CONSTRAINT asset_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public."user"(id);


--
-- Name: auction_bid auction_bid_auction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auction_bid
    ADD CONSTRAINT auction_bid_auction_id_fkey FOREIGN KEY (auction_id) REFERENCES public.auction(id);


--
-- Name: auction_bid auction_bid_bidder_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auction_bid
    ADD CONSTRAINT auction_bid_bidder_id_fkey FOREIGN KEY (bidder_id) REFERENCES public."user"(id);


--
-- Name: auction auction_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auction
    ADD CONSTRAINT auction_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public."user"(id);


--
-- Name: auction auction_winner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auction
    ADD CONSTRAINT auction_winner_id_fkey FOREIGN KEY (winner_id) REFERENCES public."user"(id);


--
-- Name: bounty bounty_placer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bounty
    ADD CONSTRAINT bounty_placer_id_fkey FOREIGN KEY (placer_id) REFERENCES public."user"(id);


--
-- Name: bounty bounty_target_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bounty
    ADD CONSTRAINT bounty_target_id_fkey FOREIGN KEY (target_id) REFERENCES public."user"(id);


--
-- Name: combat_log combat_log_attacker_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.combat_log
    ADD CONSTRAINT combat_log_attacker_id_fkey FOREIGN KEY (attacker_id) REFERENCES public."user"(id);


--
-- Name: combat_log combat_log_defender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.combat_log
    ADD CONSTRAINT combat_log_defender_id_fkey FOREIGN KEY (defender_id) REFERENCES public."user"(id);


--
-- Name: combat_log combat_log_winner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.combat_log
    ADD CONSTRAINT combat_log_winner_id_fkey FOREIGN KEY (winner_id) REFERENCES public."user"(id);


--
-- Name: config_log config_log_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.config_log
    ADD CONSTRAINT config_log_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public."user"(id);


--
-- Name: crime_lobby crime_lobby_crime_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crime_lobby
    ADD CONSTRAINT crime_lobby_crime_id_fkey FOREIGN KEY (crime_id) REFERENCES public.organized_crime(id);


--
-- Name: crime_lobby crime_lobby_leader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crime_lobby
    ADD CONSTRAINT crime_lobby_leader_id_fkey FOREIGN KEY (leader_id) REFERENCES public."user"(id);


--
-- Name: crime crime_reward_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crime
    ADD CONSTRAINT crime_reward_item_id_fkey FOREIGN KEY (reward_item_id) REFERENCES public.item(id);


--
-- Name: elite_title_seat elite_title_seat_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.elite_title_seat
    ADD CONSTRAINT elite_title_seat_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: factory_job factory_job_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.factory_job
    ADD CONSTRAINT factory_job_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: farm_job farm_job_output_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.farm_job
    ADD CONSTRAINT farm_job_output_item_id_fkey FOREIGN KEY (output_item_id) REFERENCES public.item(id);


--
-- Name: farm_job farm_job_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.farm_job
    ADD CONSTRAINT farm_job_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: farm_supply_contract farm_supply_contract_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.farm_supply_contract
    ADD CONSTRAINT farm_supply_contract_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.location(id);


--
-- Name: farm_supply_contract farm_supply_contract_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.farm_supply_contract
    ADD CONSTRAINT farm_supply_contract_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: gang fk_gang_leader_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang
    ADD CONSTRAINT fk_gang_leader_id FOREIGN KEY (leader_id) REFERENCES public."user"(id);


--
-- Name: gang fk_gang_underboss_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang
    ADD CONSTRAINT fk_gang_underboss_id FOREIGN KEY (underboss_id) REFERENCES public."user"(id);


--
-- Name: user fk_user_gang_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT fk_user_gang_id FOREIGN KEY (gang_id) REFERENCES public.gang(id);


--
-- Name: forum_post forum_post_topic_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_post
    ADD CONSTRAINT forum_post_topic_id_fkey FOREIGN KEY (topic_id) REFERENCES public.forum_topic(id);


--
-- Name: forum_post forum_post_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_post
    ADD CONSTRAINT forum_post_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: forum_topic forum_topic_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_topic
    ADD CONSTRAINT forum_topic_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.forum_category(id);


--
-- Name: forum_topic forum_topic_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_topic
    ADD CONSTRAINT forum_topic_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: futures_position futures_position_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.futures_position
    ADD CONSTRAINT futures_position_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.market_asset(id);


--
-- Name: futures_position futures_position_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.futures_position
    ADD CONSTRAINT futures_position_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: game_log game_log_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.game_log
    ADD CONSTRAINT game_log_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public."user"(id);


--
-- Name: gang_alliance gang_alliance_gang1_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_alliance
    ADD CONSTRAINT gang_alliance_gang1_id_fkey FOREIGN KEY (gang1_id) REFERENCES public.gang(id);


--
-- Name: gang_alliance gang_alliance_gang2_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_alliance
    ADD CONSTRAINT gang_alliance_gang2_id_fkey FOREIGN KEY (gang2_id) REFERENCES public.gang(id);


--
-- Name: gang_invite gang_invite_gang_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_invite
    ADD CONSTRAINT gang_invite_gang_id_fkey FOREIGN KEY (gang_id) REFERENCES public.gang(id);


--
-- Name: gang_invite gang_invite_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_invite
    ADD CONSTRAINT gang_invite_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: gang_log gang_log_gang_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_log
    ADD CONSTRAINT gang_log_gang_id_fkey FOREIGN KEY (gang_id) REFERENCES public.gang(id);


--
-- Name: gang_log gang_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_log
    ADD CONSTRAINT gang_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: gang_war gang_war_gang1_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_war
    ADD CONSTRAINT gang_war_gang1_id_fkey FOREIGN KEY (gang1_id) REFERENCES public.gang(id);


--
-- Name: gang_war gang_war_gang2_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_war
    ADD CONSTRAINT gang_war_gang2_id_fkey FOREIGN KEY (gang2_id) REFERENCES public.gang(id);


--
-- Name: gang_war gang_war_winner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gang_war
    ADD CONSTRAINT gang_war_winner_id_fkey FOREIGN KEY (winner_id) REFERENCES public.gang(id);


--
-- Name: hostess_chat_messages hostess_chat_messages_hostess_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostess_chat_messages
    ADD CONSTRAINT hostess_chat_messages_hostess_id_fkey FOREIGN KEY (hostess_id) REFERENCES public.hostesses(id);


--
-- Name: hostess_knowledge hostess_knowledge_hostess_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostess_knowledge
    ADD CONSTRAINT hostess_knowledge_hostess_id_fkey FOREIGN KEY (hostess_id) REFERENCES public.hostesses(id);


--
-- Name: hostess_memories hostess_memories_hostess_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostess_memories
    ADD CONSTRAINT hostess_memories_hostess_id_fkey FOREIGN KEY (hostess_id) REFERENCES public.hostesses(id);


--
-- Name: hostesses hostesses_current_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.hostesses
    ADD CONSTRAINT hostesses_current_player_id_fkey FOREIGN KEY (current_player_id) REFERENCES public."user"(id);


--
-- Name: investigation_log investigation_log_investigator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.investigation_log
    ADD CONSTRAINT investigation_log_investigator_id_fkey FOREIGN KEY (investigator_id) REFERENCES public."user"(id);


--
-- Name: investigation_log investigation_log_target_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.investigation_log
    ADD CONSTRAINT investigation_log_target_id_fkey FOREIGN KEY (target_id) REFERENCES public."user"(id);


--
-- Name: lobby_participant lobby_participant_lobby_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobby_participant
    ADD CONSTRAINT lobby_participant_lobby_id_fkey FOREIGN KEY (lobby_id) REFERENCES public.crime_lobby(id);


--
-- Name: lobby_participant lobby_participant_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobby_participant
    ADD CONSTRAINT lobby_participant_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: message message_receiver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.message
    ADD CONSTRAINT message_receiver_id_fkey FOREIGN KEY (receiver_id) REFERENCES public."user"(id);


--
-- Name: message message_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.message
    ADD CONSTRAINT message_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public."user"(id);


--
-- Name: money_sink_log money_sink_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.money_sink_log
    ADD CONSTRAINT money_sink_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: notification notification_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: payment_transaction payment_transaction_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payment_transaction
    ADD CONSTRAINT payment_transaction_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: race race_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.race
    ADD CONSTRAINT race_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES public."user"(id);


--
-- Name: race_participant race_participant_race_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.race_participant
    ADD CONSTRAINT race_participant_race_id_fkey FOREIGN KEY (race_id) REFERENCES public.race(id);


--
-- Name: race_participant race_participant_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.race_participant
    ADD CONSTRAINT race_participant_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: race_participant race_participant_user_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.race_participant
    ADD CONSTRAINT race_participant_user_vehicle_id_fkey FOREIGN KEY (user_vehicle_id) REFERENCES public.user_vehicle(id);


--
-- Name: referral referral_referred_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.referral
    ADD CONSTRAINT referral_referred_id_fkey FOREIGN KEY (referred_id) REFERENCES public."user"(id);


--
-- Name: referral referral_referrer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.referral
    ADD CONSTRAINT referral_referrer_id_fkey FOREIGN KEY (referrer_id) REFERENCES public."user"(id);


--
-- Name: resurrection_request resurrection_request_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resurrection_request
    ADD CONSTRAINT resurrection_request_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: spot_order spot_order_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.spot_order
    ADD CONSTRAINT spot_order_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.market_asset(id);


--
-- Name: spot_order spot_order_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.spot_order
    ADD CONSTRAINT spot_order_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user_achievement user_achievement_achievement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_achievement
    ADD CONSTRAINT user_achievement_achievement_id_fkey FOREIGN KEY (achievement_id) REFERENCES public.achievement(id);


--
-- Name: user_achievement user_achievement_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_achievement
    ADD CONSTRAINT user_achievement_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user_crime_cooldown user_crime_cooldown_crime_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_crime_cooldown
    ADD CONSTRAINT user_crime_cooldown_crime_id_fkey FOREIGN KEY (crime_id) REFERENCES public.crime(id);


--
-- Name: user_crime_cooldown user_crime_cooldown_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_crime_cooldown
    ADD CONSTRAINT user_crime_cooldown_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user_daily_task user_daily_task_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_daily_task
    ADD CONSTRAINT user_daily_task_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.daily_task(id);


--
-- Name: user_daily_task user_daily_task_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_daily_task
    ADD CONSTRAINT user_daily_task_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user_facility user_facility_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_facility
    ADD CONSTRAINT user_facility_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user_investment user_investment_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_investment
    ADD CONSTRAINT user_investment_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.market_asset(id);


--
-- Name: user_investment user_investment_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_investment
    ADD CONSTRAINT user_investment_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user_item user_item_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_item
    ADD CONSTRAINT user_item_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.item(id);


--
-- Name: user_item user_item_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_item
    ADD CONSTRAINT user_item_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user user_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.location(id);


--
-- Name: user_log user_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_log
    ADD CONSTRAINT user_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user_progress user_progress_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_progress
    ADD CONSTRAINT user_progress_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user_vehicle user_vehicle_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_vehicle
    ADD CONSTRAINT user_vehicle_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user_vehicle user_vehicle_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_vehicle
    ADD CONSTRAINT user_vehicle_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicle(id);


--
-- Name: weekly_winner weekly_winner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.weekly_winner
    ADD CONSTRAINT weekly_winner_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--

\unrestrict Qh9BYuCU0LAOH1PvAkskGRzcNThy07z1bj8i1SeSvVay7p36dLWjWtrNrzK5YEU

