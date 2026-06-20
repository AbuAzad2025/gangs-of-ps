
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9124fe2bf48a'
down_revision = '380a7cb143ee'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    def ensure_index(name, table, cols, unique=False):
        if table not in tables:
            return
        cols_sql = ", ".join([f'"{c}"' for c in cols])
        unique_sql = "UNIQUE " if unique else ""
        op.execute(
            sa.text(
                f'CREATE {unique_sql}INDEX IF NOT EXISTS "{name}" ON "{table}" ({cols_sql})'))

    if 'game_rooms' not in tables:
        op.create_table(
            'game_rooms',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('game_type', sa.String(length=20), nullable=False),
            sa.Column('name', sa.String(length=64), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('game_state', sa.JSON(), nullable=True),
            sa.Column('currency_type', sa.String(length=20), nullable=True),
            sa.Column('stake_amount', sa.BigInteger(), nullable=True),
            sa.Column('pot_amount', sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        tables.add('game_rooms')

    if 'game_players' not in tables:
        op.create_table(
            'game_players',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('room_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('joined_at', sa.DateTime(), nullable=True),
            sa.Column('seat_index', sa.Integer(), nullable=True),
            sa.Column('is_ready', sa.Boolean(), nullable=True),
            sa.ForeignKeyConstraint(['room_id'], ['game_rooms.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        tables.add('game_players')

    if 'game_chat' not in tables:
        op.create_table(
            'game_chat',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('room_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('message', sa.String(length=500), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['room_id'], ['game_rooms.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        tables.add('game_chat')

    ensure_index('ix_active_intel_target_id', 'active_intel', ['target_id'])
    ensure_index('ix_active_intel_user_id', 'active_intel', ['user_id'])
    ensure_index('ix_asset_gang_id', 'asset', ['gang_id'])
    ensure_index('ix_asset_owner_id', 'asset', ['owner_id'])
    ensure_index('ix_auction_end_time', 'auction', ['end_time'])
    ensure_index('ix_auction_seller_id', 'auction', ['seller_id'])
    ensure_index('ix_auction_status', 'auction', ['status'])
    ensure_index('ix_auction_winner_id', 'auction', ['winner_id'])
    ensure_index('ix_auction_bid_timestamp', 'auction_bid', ['timestamp'])
    ensure_index('ix_bounty_placer_id', 'bounty', ['placer_id'])
    ensure_index('ix_bounty_target_id', 'bounty', ['target_id'])
    ensure_index('ix_combat_log_attacker_id', 'combat_log', ['attacker_id'])
    ensure_index('ix_combat_log_defender_id', 'combat_log', ['defender_id'])
    ensure_index('ix_combat_log_timestamp', 'combat_log', ['timestamp'])
    ensure_index('ix_combat_log_winner_id', 'combat_log', ['winner_id'])
    ensure_index('ix_crime_cooldown', 'crime', ['cooldown'])
    ensure_index('ix_crime_is_active', 'crime', ['is_active'])
    ensure_index('ix_crime_min_level', 'crime', ['min_level'])
    ensure_index('ix_crime_reward_item_id', 'crime', ['reward_item_id'])
    ensure_index('ix_crime_lobby_created_at', 'crime_lobby', ['created_at'])
    ensure_index('ix_crime_lobby_crime_id', 'crime_lobby', ['crime_id'])
    ensure_index('idx_crime_lobby_status_created',
                 'crime_lobby', ['status', 'created_at'])
    ensure_index('ix_farm_job_output_item_id', 'farm_job', ['output_item_id'])
    ensure_index('ix_forum_post_topic_id', 'forum_post', ['topic_id'])
    ensure_index('ix_forum_post_user_id', 'forum_post', ['user_id'])
    ensure_index('idx_futures_liq_check', 'futures_position', [
                 'asset_id', 'is_open', 'position_type', 'liquidation_price'])
    ensure_index('idx_futures_position_user_open',
                 'futures_position', ['user_id', 'is_open'])
    ensure_index(
        'ix_futures_position_asset_id',
        'futures_position',
        ['asset_id'])
    ensure_index(
        'ix_futures_position_closed_at',
        'futures_position',
        ['closed_at'])
    ensure_index(
        'ix_futures_position_is_open',
        'futures_position',
        ['is_open'])
    ensure_index('ix_futures_position_liquidation_price',
                 'futures_position', ['liquidation_price'])
    ensure_index(
        'ix_futures_position_opened_at',
        'futures_position',
        ['opened_at'])
    ensure_index(
        'ix_futures_position_position_type',
        'futures_position',
        ['position_type'])
    ensure_index('ix_game_chat_room_id', 'game_chat', ['room_id'])
    ensure_index('ix_game_chat_user_id', 'game_chat', ['user_id'])
    ensure_index('ix_game_players_room_id', 'game_players', ['room_id'])
    ensure_index('ix_game_players_user_id', 'game_players', ['user_id'])
    ensure_index('ix_gang_underboss_id', 'gang', ['underboss_id'])
    ensure_index('ix_gang_alliance_gang1_id', 'gang_alliance', ['gang1_id'])
    ensure_index('ix_gang_alliance_gang2_id', 'gang_alliance', ['gang2_id'])
    ensure_index('ix_gang_item_gang_id', 'gang_item', ['gang_id'])
    ensure_index('ix_gang_item_item_id', 'gang_item', ['item_id'])
    ensure_index('ix_gang_log_gang_id', 'gang_log', ['gang_id'])
    ensure_index('ix_gang_log_user_id', 'gang_log', ['user_id'])
    ensure_index('ix_gang_war_gang1_id', 'gang_war', ['gang1_id'])
    ensure_index('ix_gang_war_gang2_id', 'gang_war', ['gang2_id'])
    ensure_index('ix_gang_war_winner_id', 'gang_war', ['winner_id'])
    ensure_index(
        'ix_heist_history_created_at',
        'heist_history',
        ['created_at'])
    ensure_index(
        'ix_hostess_knowledge_hostess_id',
        'hostess_knowledge',
        ['hostess_id'])
    ensure_index('ix_market_asset_asset_type', 'market_asset', ['asset_type'])
    ensure_index('ix_message_sender_id', 'message', ['sender_id'])
    ensure_index('ix_notification_user_id', 'notification', ['user_id'])
    ensure_index(
        'ix_organized_crime_is_active',
        'organized_crime',
        ['is_active'])
    ensure_index(
        'ix_organized_crime_min_gang_level',
        'organized_crime',
        ['min_gang_level'])
    ensure_index(
        'ix_organized_crime_min_level',
        'organized_crime',
        ['min_level'])
    ensure_index(
        'ix_payment_transaction_user_id',
        'payment_transaction',
        ['user_id'])
    ensure_index('ix_public_chat_user_id', 'public_chat', ['user_id'])
    ensure_index('ix_race_creator_id', 'race', ['creator_id'])
    ensure_index(
        'ix_race_participant_race_id',
        'race_participant',
        ['race_id'])
    ensure_index(
        'ix_race_participant_user_id',
        'race_participant',
        ['user_id'])
    ensure_index(
        'ix_race_participant_user_vehicle_id',
        'race_participant',
        ['user_vehicle_id'])
    ensure_index('ix_referral_referred_id', 'referral', ['referred_id'])
    ensure_index('ix_referral_referrer_id', 'referral', ['referrer_id'])
    ensure_index('idx_spot_order_exec_buy', 'spot_order', [
                 'asset_id', 'status', 'order_type', 'price'])
    ensure_index('ix_spot_order_created_at', 'spot_order', ['created_at'])
    ensure_index('ix_user_active_hostess_id', 'user', ['active_hostess_id'])
    ensure_index('ix_user_created_at', 'user', ['created_at'])
    ensure_index('ix_user_heat_updated_at', 'user', ['heat_updated_at'])
    ensure_index('ix_user_last_crime', 'user', ['last_crime'])
    ensure_index('ix_user_last_daily_reward', 'user', ['last_daily_reward'])
    ensure_index('ix_user_last_travel', 'user', ['last_travel'])
    ensure_index('ix_user_referred_by_id', 'user', ['referred_by_id'])
    ensure_index(
        'ix_user_crime_cooldown_cooldown_until',
        'user_crime_cooldown',
        ['cooldown_until'])
    ensure_index(
        'ix_user_crime_cooldown_crime_id',
        'user_crime_cooldown',
        ['crime_id'])
    ensure_index(
        'ix_user_crime_cooldown_user_id',
        'user_crime_cooldown',
        ['user_id'])
    ensure_index('idx_user_crime_cooldown_user_crime',
                 'user_crime_cooldown', ['user_id', 'crime_id'])
    ensure_index('ix_user_daily_task_task_id', 'user_daily_task', ['task_id'])
    ensure_index('ix_user_daily_task_user_id', 'user_daily_task', ['user_id'])
    ensure_index(
        'idx_user_investment_user_asset', 'user_investment', [
            'user_id', 'asset_id'], unique=True)
    ensure_index(
        'ix_user_investment_asset_id',
        'user_investment',
        ['asset_id'])
    ensure_index('ix_user_item_item_id', 'user_item', ['item_id'])
    ensure_index('ix_user_item_user_id', 'user_item', ['user_id'])
    ensure_index(
        'idx_user_org_crime_cooldown_user_crime', 'user_organized_crime_cooldown', [
            'user_id', 'crime_id'], unique=True)
    ensure_index('ix_user_organized_crime_cooldown_cooldown_until',
                 'user_organized_crime_cooldown', ['cooldown_until'])
    ensure_index('ix_user_organized_crime_cooldown_crime_id',
                 'user_organized_crime_cooldown', ['crime_id'])
    ensure_index('ix_user_organized_crime_cooldown_user_id',
                 'user_organized_crime_cooldown', ['user_id'])
    ensure_index('ix_user_progress_user_id', 'user_progress', ['user_id'])
    ensure_index('ix_user_vehicle_user_id', 'user_vehicle', ['user_id'])
    ensure_index('ix_user_vehicle_vehicle_id', 'user_vehicle', ['vehicle_id'])
    ensure_index('ix_weekly_winner_user_id', 'weekly_winner', ['user_id'])

    with op.batch_alter_table('hostess_chat_messages', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_hostess_chat_messages_user_id',
            'user',
            ['user_id'],
            ['id'])

    with op.batch_alter_table('hostess_memories', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_hostess_memories_user_id',
            'user',
            ['user_id'],
            ['id'])

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_user_active_hostess_id',
            'hostesses',
            ['active_hostess_id'],
            ['id'])


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('weekly_winner', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_weekly_winner_user_id'))

    with op.batch_alter_table('user_vehicle', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_vehicle_vehicle_id'))
        batch_op.drop_index(batch_op.f('ix_user_vehicle_user_id'))

    with op.batch_alter_table('user_progress', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_progress_user_id'))

    with op.batch_alter_table('user_organized_crime_cooldown', schema=None) as batch_op:
        batch_op.drop_index(
            batch_op.f('ix_user_organized_crime_cooldown_user_id'))
        batch_op.drop_index(
            batch_op.f('ix_user_organized_crime_cooldown_crime_id'))
        batch_op.drop_index(
            batch_op.f('ix_user_organized_crime_cooldown_cooldown_until'))
        batch_op.drop_index('idx_user_org_crime_cooldown_user_crime')

    with op.batch_alter_table('user_item', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_item_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_item_item_id'))

    with op.batch_alter_table('user_investment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_investment_asset_id'))
        batch_op.drop_index('idx_user_investment_user_asset')

    with op.batch_alter_table('user_daily_task', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_daily_task_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_daily_task_task_id'))

    with op.batch_alter_table('user_crime_cooldown', schema=None) as batch_op:
        batch_op.drop_index('idx_user_crime_cooldown_user_crime')
        batch_op.drop_index(batch_op.f('ix_user_crime_cooldown_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_crime_cooldown_crime_id'))
        batch_op.drop_index(
            batch_op.f('ix_user_crime_cooldown_cooldown_until'))

    with op.batch_alter_table('user', schema=None) as batch_op:
        # SQLite may not have named constraints; Alembic expects a name when
        # dropping constraints, otherwise it raises:
        # "ValueError: Constraint must have a name".
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        try:
            fks = inspector.get_foreign_keys('user')
        except Exception:
            fks = []

        for fk in fks:
            # Different dialects return different shapes; only drop constraints
            # that Alembic can identify via a real constraint name.
            fk_name = fk.get('name')
            if fk_name:
                batch_op.drop_constraint(fk_name, type_='foreignkey')

        batch_op.drop_index(batch_op.f('ix_user_referred_by_id'))
        batch_op.drop_index(batch_op.f('ix_user_last_travel'))
        batch_op.drop_index(batch_op.f('ix_user_last_daily_reward'))
        batch_op.drop_index(batch_op.f('ix_user_last_crime'))
        batch_op.drop_index(batch_op.f('ix_user_heat_updated_at'))
        batch_op.drop_index(batch_op.f('ix_user_created_at'))
        batch_op.drop_index(batch_op.f('ix_user_active_hostess_id'))

    with op.batch_alter_table('spot_order', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_spot_order_created_at'))
        batch_op.drop_index('idx_spot_order_exec_buy')

    with op.batch_alter_table('referral', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_referral_referrer_id'))
        batch_op.drop_index(batch_op.f('ix_referral_referred_id'))

    with op.batch_alter_table('race_participant', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_race_participant_user_vehicle_id'))
        batch_op.drop_index(batch_op.f('ix_race_participant_user_id'))
        batch_op.drop_index(batch_op.f('ix_race_participant_race_id'))

    with op.batch_alter_table('race', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_race_creator_id'))

    with op.batch_alter_table('public_chat', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_public_chat_user_id'))

    with op.batch_alter_table('payment_transaction', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_transaction_user_id'))

    with op.batch_alter_table('organized_crime', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_organized_crime_min_level'))
        batch_op.drop_index(batch_op.f('ix_organized_crime_min_gang_level'))
        batch_op.drop_index(batch_op.f('ix_organized_crime_is_active'))

    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notification_user_id'))

    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_message_sender_id'))

    with op.batch_alter_table('market_asset', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_market_asset_asset_type'))

    with op.batch_alter_table('hostess_memories', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')

    with op.batch_alter_table('hostess_knowledge', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_hostess_knowledge_hostess_id'))

    with op.batch_alter_table('hostess_chat_messages', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')

    with op.batch_alter_table('heist_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_heist_history_created_at'))

    with op.batch_alter_table('gang_war', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gang_war_winner_id'))
        batch_op.drop_index(batch_op.f('ix_gang_war_gang2_id'))
        batch_op.drop_index(batch_op.f('ix_gang_war_gang1_id'))

    with op.batch_alter_table('gang_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gang_log_user_id'))
        batch_op.drop_index(batch_op.f('ix_gang_log_gang_id'))

    with op.batch_alter_table('gang_item', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gang_item_item_id'))
        batch_op.drop_index(batch_op.f('ix_gang_item_gang_id'))

    with op.batch_alter_table('gang_alliance', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gang_alliance_gang2_id'))
        batch_op.drop_index(batch_op.f('ix_gang_alliance_gang1_id'))

    with op.batch_alter_table('gang', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gang_underboss_id'))

    with op.batch_alter_table('game_players', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_game_players_user_id'))
        batch_op.drop_index(batch_op.f('ix_game_players_room_id'))

    with op.batch_alter_table('game_chat', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_game_chat_user_id'))
        batch_op.drop_index(batch_op.f('ix_game_chat_room_id'))

    with op.batch_alter_table('futures_position', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_futures_position_opened_at'))
        batch_op.drop_index(
            batch_op.f('ix_futures_position_liquidation_price'))
        batch_op.drop_index(batch_op.f('ix_futures_position_is_open'))
        batch_op.drop_index(batch_op.f('ix_futures_position_closed_at'))
        batch_op.drop_index(batch_op.f('ix_futures_position_asset_id'))
        batch_op.drop_index('idx_futures_position_user_open')
        batch_op.drop_index('idx_futures_liq_check')
        batch_op.drop_index(batch_op.f('ix_futures_position_position_type'))

    with op.batch_alter_table('forum_post', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_forum_post_user_id'))
        batch_op.drop_index(batch_op.f('ix_forum_post_topic_id'))

    with op.batch_alter_table('farm_job', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_farm_job_output_item_id'))

    with op.batch_alter_table('crime_lobby', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_crime_lobby_crime_id'))
        batch_op.drop_index(batch_op.f('ix_crime_lobby_created_at'))
        batch_op.drop_index('idx_crime_lobby_status_created')

    with op.batch_alter_table('crime', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_crime_reward_item_id'))
        batch_op.drop_index(batch_op.f('ix_crime_min_level'))
        batch_op.drop_index(batch_op.f('ix_crime_is_active'))
        batch_op.drop_index(batch_op.f('ix_crime_cooldown'))

    with op.batch_alter_table('combat_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_combat_log_winner_id'))
        batch_op.drop_index(batch_op.f('ix_combat_log_timestamp'))
        batch_op.drop_index(batch_op.f('ix_combat_log_defender_id'))
        batch_op.drop_index(batch_op.f('ix_combat_log_attacker_id'))

    with op.batch_alter_table('bounty', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bounty_target_id'))
        batch_op.drop_index(batch_op.f('ix_bounty_placer_id'))

    with op.batch_alter_table('auction_bid', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_auction_bid_timestamp'))

    with op.batch_alter_table('auction', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_auction_winner_id'))
        batch_op.drop_index(batch_op.f('ix_auction_status'))
        batch_op.drop_index(batch_op.f('ix_auction_seller_id'))
        batch_op.drop_index(batch_op.f('ix_auction_end_time'))

    with op.batch_alter_table('asset', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_asset_owner_id'))
        batch_op.drop_index(batch_op.f('ix_asset_gang_id'))

    with op.batch_alter_table('active_intel', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_active_intel_user_id'))
        batch_op.drop_index(batch_op.f('ix_active_intel_target_id'))

    # ### end Alembic commands ###
