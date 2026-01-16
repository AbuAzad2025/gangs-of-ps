from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    jsonify,
    current_app,
    Response,
    stream_with_context,
)
from flask_login import login_required, current_user
from flask_babel import gettext as _
from sqlalchemy.orm.attributes import flag_modified
from extensions import db, socketio
from models import UserLog
from models.entertainment import GameRoom, GamePlayer, GameChat
from models.user import User
from routes.trix_logic import TrixGameLogic
from routes.tarneeb_logic import TarneebGameLogic
from routes.entertainment_helpers import _distribute_prizes
from models.system import SystemConfig
from services.resource_service import ResourceService
import json
import time
import chess
import math
from flask import abort
if socketio:
    from flask_socketio import join_room, leave_room

bp = Blueprint('entertainment', __name__, url_prefix='/entertainment')


@bp.route('/')
@login_required
def index():
    if SystemConfig.get_value('entertainment_enabled', 'true') != 'true':
        flash(_('قسم الترفيه معطل حالياً'), 'warning')
        return redirect(url_for('main.hara'))
    # Optimization: Limit rooms to prevent memory overload
    rooms = GameRoom.query.filter(
        GameRoom.status != 'finished').order_by(
        GameRoom.created_at.desc()).limit(50).all()
    return render_template('entertainment/index.html', rooms=rooms)


@bp.route('/create_room', methods=['POST'])
@login_required
def create_room():
    game_type = request.form.get('game_type')
    name = request.form.get('name')
    mode = request.form.get('mode', 'multiplayer')
    trix_style = request.form.get('trix_style', 'kingdoms')
    trix_team_mode = request.form.get('trix_team_mode', 'individual')

    # Enhanced input validation
    if not game_type or game_type not in ['chess', 'trix', 'tarneeb']:
        flash(_('نوع اللعبة غير صالح'), 'danger')
        return redirect(url_for('entertainment.index'))

    if not name or len(name.strip()) < 3 or len(name.strip()) > 50:
        flash(_('اسم الغرفة يجب أن يكون بين 3 و 50 حرفاً'), 'danger')
        return redirect(url_for('entertainment.index'))

    if mode not in ['solo', 'multiplayer']:
        flash(_('وضع اللعب غير صالح'), 'danger')
        return redirect(url_for('entertainment.index'))

    # Betting params
    currency_type = request.form.get('currency_type', 'money')
    try:
        stake_amount = int(request.form.get('stake_amount', 0))
        if stake_amount < 0 or stake_amount > 1000000000:  # Max limit
            raise ValueError("Invalid stake amount")
    except ValueError:
        stake_amount = 0

    if stake_amount < 0:
        flash(_('مبلغ الرهان غير صالح'), 'danger')
        return redirect(url_for('entertainment.index'))

    allowed_curr = (
        SystemConfig.get_value(
            'betting_allowed_currencies',
            'money,diamonds') or 'money,diamonds').split(',')
    allowed_curr = [c.strip() for c in allowed_curr if c.strip()]
    if currency_type not in allowed_curr:
        flash(_('نوع العملة غير صالح'), 'danger')
        return redirect(url_for('entertainment.index'))

    if not game_type or not name:
        flash(_('الرجاء تعبئة جميع الحقول'), 'danger')
        return redirect(url_for('entertainment.index'))

    if SystemConfig.get_value('entertainment_enabled', 'true') != 'true':
        flash(_('قسم الترفيه معطل حالياً'), 'warning')
        return redirect(url_for('entertainment.index'))

    game_enabled_key = {
        'chess': 'game_chess_enabled',
        'trix': 'game_trix_enabled',
        'tarneeb': 'game_tarneeb_enabled'
    }.get(game_type, None)
    if game_enabled_key and SystemConfig.get_value(
            game_enabled_key, 'true') != 'true':
        flash(_('هذه اللعبة معطلة حالياً'), 'warning')
        return redirect(url_for('entertainment.index'))

    if SystemConfig.get_value('betting_enabled', 'true') != 'true':
        stake_amount = 0
        currency_type = 'money'

    try:
        min_stake = int(
            SystemConfig.get_value(
                'betting_min_stake',
                '0') or '0')
    except Exception:
        min_stake = 0
    try:
        max_stake = int(
            SystemConfig.get_value(
                'betting_max_stake',
                '1000000000') or '1000000000')
    except Exception:
        max_stake = 1000000000
    if stake_amount < min_stake:
        flash(_('الرهان أقل من الحد الأدنى'), 'danger')
        return redirect(url_for('entertainment.index'))
    if stake_amount > max_stake:
        flash(_('الرهان يتجاوز الحد الأقصى'), 'danger')
        return redirect(url_for('entertainment.index'))

    # Check creator balance for stake
    if stake_amount > 0:
        # Lock user row to prevent double spending
        try:
            user = db.session.query(User).filter_by(
                id=current_user.id).with_for_update().first()
        except Exception:
            # Fallback for DBs that don't support with_for_update or if it
            # fails
            user = User.query.get(current_user.id)

        if currency_type == 'money' and user.money < stake_amount:
            flash(_('لا تملك رصيد كافي لإنشاء الغرفة'), 'danger')
            return redirect(url_for('entertainment.index'))
        elif currency_type == 'diamonds' and user.diamonds < stake_amount:
            flash(_('لا تملك ماس كافي لإنشاء الغرفة'), 'danger')
            return redirect(url_for('entertainment.index'))

    # Determine Status and State based on Mode
    if mode == 'solo':
        status = 'playing'
        room = GameRoom(
            game_type=game_type,
            name=name,
            status=status,
            currency_type=currency_type,
            stake_amount=stake_amount,
            pot_amount=0  # Will add stake below
        )

        if game_type == 'chess':
            room.game_state = {
                'fen': chess.STARTING_FEN,
                'history': [],
                'turn': 'w',
                'is_solo': True,
                'engine': 'minimax'}
            if stake_amount > 0:
                room.pot_amount += stake_amount  # 1 Bot
        elif game_type == 'trix':
            room.game_state = {
                'is_solo': True,
                'bot_seats': [
                    1,
                    2,
                    3],
                'trix_style': trix_style,
                'team_mode': trix_team_mode}
            TrixGameLogic.init_game(room.game_state)
            TrixGameLogic.deal(room.game_state)  # Deal initial hand
            if trix_style == 'complex':
                room.game_state['current_contract'] = 'complex'
                room.game_state['phase'] = 'doubling'
            else:
                room.game_state['phase'] = 'choose_contract'
            if stake_amount > 0:
                room.pot_amount += (3 * stake_amount)  # 3 Bots
        elif game_type == 'tarneeb':
            room.game_state = {
                'is_solo': True, 'bot_seats': [
                    1, 2, 3], 'team_mode': 'partnership'}
            TarneebGameLogic.init_game(room.game_state)
            TarneebGameLogic.deal(room.game_state)
            if stake_amount > 0:
                room.pot_amount += (3 * stake_amount)  # 3 Bots

    else:  # Multiplayer
        status = 'waiting'
        room = GameRoom(
            game_type=game_type,
            name=name,
            status=status,
            currency_type=currency_type,
            stake_amount=stake_amount,
            pot_amount=0
        )

        if game_type == 'chess':
            room.game_state = {
                'fen': chess.STARTING_FEN,
                'history': [],
                'turn': 'w'}
        elif game_type == 'trix':
            room.game_state = {
                'phase': 'lobby',
                'players_ready': [],
                'trix_style': trix_style,
                'team_mode': trix_team_mode}
        elif game_type == 'tarneeb':
            room.game_state = {
                'phase': 'lobby',
                'players_ready': [],
                'team_mode': 'partnership'}

    db.session.add(room)
    db.session.flush()

    # Process entry fee for creator
    if stake_amount > 0:
        if currency_type == 'money':
            if not ResourceService.modify_resources(
                current_user.id, {
                    'money': -stake_amount}, 'room_create', auto_commit=False, expected_version=None):
                db.session.rollback()
                flash(_('لا تملك رصيد كافي لإنشاء الغرفة'), 'danger')
                return redirect(url_for('entertainment.index'))
        else:
            if not ResourceService.modify_resources(
                current_user.id, {
                    'diamonds': -stake_amount}, 'room_create', auto_commit=False, expected_version=None):
                db.session.rollback()
                flash(
                    _('رصيدك من الألماس غير كافي! تواصل معنا عبر الواتساب لشراء الألماس.'),
                    'warning')
                return redirect(url_for('entertainment.index'))
        room.pot_amount += stake_amount

    # Auto join creator
    player = GamePlayer(
        room_id=room.id,
        user_id=current_user.id,
        seat_index=0,
        is_ready=True)
    db.session.add(player)

    # Log room creation
    log = UserLog(
        user_id=current_user.id,
        action='ROOM_CREATE_META',
        details=json.dumps({
            'room_id': room.id,
            'room_name': room.name,
            'game_type': room.game_type,
            'mode': mode,
            'stake_amount': room.stake_amount,
            'currency_type': room.currency_type,
            'trix_style': trix_style if game_type == 'trix' else None,
            'trix_team_mode': trix_team_mode if game_type == 'trix' else None
        }),
        result='success',
        ip_address=request.remote_addr,
        user_agent=str(request.user_agent)
    )
    db.session.add(log)

    db.session.commit()

    return redirect(url_for('entertainment.room', room_id=room.id))


@bp.route('/room/<int:room_id>')
@login_required
def room(room_id):
    room = GameRoom.query.get_or_404(room_id)
    # Check if user is in room
    player = GamePlayer.query.filter_by(
        room_id=room.id, user_id=current_user.id).first()

    if not player:
        # Try to join if not full - with locking
        try:
            # Lock room to check capacity securely
            r_lock = db.session.query(GameRoom).filter_by(
                id=room.id).with_for_update().first()
            if r_lock:
                count = r_lock.players.count()
                max_players = 2 if r_lock.game_type == 'chess' else 4

                if count < max_players:
                    # Check for entry fee with user lock
                    if r_lock.stake_amount > 0:
                        if r_lock.currency_type == 'money':
                            if not ResourceService.modify_resources(
                                current_user.id,
                                {'money': -r_lock.stake_amount},
                                'room_join',
                                auto_commit=False,
                                expected_version=None,
                            ):
                                db.session.rollback()
                                flash(
                                    _('لا تملك رصيد كافي للانضمام'), 'danger')
                                return redirect(url_for('entertainment.index'))
                        elif r_lock.currency_type == 'diamonds':
                            if not ResourceService.modify_resources(
                                current_user.id,
                                {'diamonds': -r_lock.stake_amount},
                                'room_join',
                                auto_commit=False,
                                expected_version=None,
                            ):
                                db.session.rollback()
                                flash(
                                    _('رصيدك من الألماس غير كافي! تواصل معنا عبر الواتساب لشراء الألماس.'),
                                    'warning')
                                return redirect(url_for('entertainment.index'))

                        r_lock.pot_amount += r_lock.stake_amount

                    # Add player
                    new_player = GamePlayer(
                        room_id=r_lock.id,
                        user_id=current_user.id,
                        seat_index=count,
                        is_ready=False)
                    db.session.add(new_player)

                    db.session.add(UserLog(user_id=current_user.id,
                                           action='ROOM_JOIN_META',
                                           details=json.dumps({'room_id': r_lock.id,
                                                               'stake_amount': r_lock.stake_amount,
                                                               'currency_type': r_lock.currency_type}),
                                           result='success',
                                           ip_address=request.remote_addr,
                                           user_agent=str(request.user_agent)))
                    db.session.commit()

                    # Refresh original room object for rendering
                    db.session.refresh(room)
                    player = new_player
                else:
                    db.session.rollback()  # Release locks if full
                    flash(_('الغرفة ممتلئة'), 'danger')
                    return redirect(url_for('entertainment.index'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error joining room: {e}")
            flash(_('حدث خطأ أثناء الانضمام'), 'danger')
            return redirect(url_for('entertainment.index'))

    # Render specific game template if playing
    if room.status == 'playing':
        if room.game_type == 'chess':
            return render_template(
                'entertainment/chess_online.html',
                room=room,
                player=player)
        elif room.game_type == 'trix':
            return render_template(
                'entertainment/trix_online.html',
                room=room,
                player=player)
        elif room.game_type == 'tarneeb':
            return render_template(
                'entertainment/tarneeb_online.html',
                room=room,
                player=player)

    return render_template(
        'entertainment/lobby_room.html',
        room=room,
        player=player)


def _chess_piece_value(piece_type):
    if piece_type == chess.PAWN:
        return 100
    if piece_type == chess.KNIGHT:
        return 320
    if piece_type == chess.BISHOP:
        return 330
    if piece_type == chess.ROOK:
        return 500
    if piece_type == chess.QUEEN:
        return 900
    if piece_type == chess.KING:
        return 0
    return 0


def _chess_evaluate(board: chess.Board):
    if board.is_checkmate():
        return -100000 if board.turn else 100000
    psq_p = [
        0, 5, 5, 0, 5, 10, 50, 0,
        0, 10, -5, 0, 5, 10, 50, 0,
        0, 10, -10, 0, 10, 20, 50, 0,
        0, -20, 0, 20, 25, 30, 50, 0,
        0, -20, 0, 20, 25, 30, 50, 0,
        0, 10, -10, 0, 10, 20, 50, 0,
        0, 10, -5, 0, 5, 10, 50, 0,
        0, 5, 5, 0, 5, 10, 50, 0,
    ]
    psq_n = [
        -50, -40, -30, -30, -30, -30, -40, -50,
        -40, -20, 0, 5, 0, 5, -20, -40,
        -30, 5, 10, 15, 15, 10, 5, -30,
        -30, 0, 15, 20, 20, 15, 0, -30,
        -30, 5, 15, 20, 20, 15, 5, -30,
        -30, 0, 10, 15, 15, 10, 0, -30,
        -40, -20, 0, 0, 0, 0, -20, -40,
        -50, -40, -30, -30, -30, -30, -40, -50,
    ]
    psq_b = [
        -20, -10, -10, -10, -10, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 5, 10, 15, 15, 10, 5, -10,
        -10, 5, 10, 15, 15, 10, 5, -10,
        -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -20, -10, -10, -10, -10, -10, -10, -20,
    ]
    psq_r = [
        0, 0, 5, 10, 10, 5, 0, 0,
        0, 0, 5, 10, 10, 5, 0, 0,
        0, 0, 5, 10, 10, 5, 0, 0,
        0, 0, 5, 10, 10, 5, 0, 0,
        0, 0, 5, 10, 10, 5, 0, 0,
        0, 0, 5, 10, 10, 5, 0, 0,
        25, 25, 25, 25, 25, 25, 25, 25,
        0, 0, 5, 10, 10, 5, 0, 0,
    ]
    psq_q = [
        -10, -5, -5, 0, 0, -5, -5, -10,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 5, 5, 5, 5, 0, -5,
        0, 0, 5, 5, 5, 5, 0, 0,
        -5, 0, 5, 5, 5, 5, 0, -5,
        -5, 0, 5, 5, 5, 5, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -10, -5, -5, 0, 0, -5, -5, -10,
    ]
    psq_k = [
        20, 30, 10, 0, 0, 10, 30, 20,
        20, 20, 0, 0, 0, 0, 20, 20,
        -10, -20, -20, -20, -20, -20, -20, -10,
        -20, -30, -30, -40, -40, -30, -30, -20,
        -20, -30, -30, -40, -40, -30, -30, -20,
        -10, -20, -20, -20, -20, -20, -20, -10,
        20, 20, 0, 0, 0, 0, 20, 20,
        20, 30, 10, 0, 0, 10, 30, 20,
    ]
    score = 0
    for piece_type in [
            chess.PAWN,
            chess.KNIGHT,
            chess.BISHOP,
            chess.ROOK,
            chess.QUEEN]:
        score += len(board.pieces(piece_type, chess.WHITE)) * \
            _chess_piece_value(piece_type)
        score -= len(board.pieces(piece_type, chess.BLACK)) * \
            _chess_piece_value(piece_type)
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p:
            continue
        idx = sq if p.color == chess.WHITE else chess.square_mirror(sq)
        if p.piece_type == chess.PAWN:
            score += psq_p[idx] if p.color == chess.WHITE else -psq_p[idx]
        elif p.piece_type == chess.KNIGHT:
            score += psq_n[idx] if p.color == chess.WHITE else -psq_n[idx]
        elif p.piece_type == chess.BISHOP:
            score += psq_b[idx] if p.color == chess.WHITE else -psq_b[idx]
        elif p.piece_type == chess.ROOK:
            score += psq_r[idx] if p.color == chess.WHITE else -psq_r[idx]
        elif p.piece_type == chess.QUEEN:
            score += psq_q[idx] if p.color == chess.WHITE else -psq_q[idx]
        elif p.piece_type == chess.KING:
            score += psq_k[idx] if p.color == chess.WHITE else -psq_k[idx]
    score += len(list(board.legal_moves)) * 1
    return score if board.turn == chess.WHITE else -score


def _chess_order_moves(board: chess.Board):
    def move_score(m):
        if board.is_capture(m):
            victim = board.piece_at(m.to_square)
            attacker = board.piece_at(m.from_square)
            v = _chess_piece_value(victim.piece_type) if victim else 0
            a = _chess_piece_value(attacker.piece_type) if attacker else 0
            return 10000 + v - a
        board.push(m)
        sc = 10 if board.is_check() else 0
        board.pop()
        return sc
    moves = list(board.legal_moves)
    moves.sort(key=move_score, reverse=True)
    return moves


def _chess_minimax(
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        maximizing: bool,
        nodes: dict):
    # Safety limit
    nodes['count'] += 1
    if nodes['count'] > 5000:  # Max 5000 nodes check per move to prevent hangs
        return _chess_evaluate(board), None

    if depth == 0 or board.is_game_over():
        return _chess_evaluate(board), None
    best_move = None
    if maximizing:
        max_eval = -math.inf
        for move in _chess_order_moves(board):
            board.push(move)
            eval_score, _ = _chess_minimax(
                board, depth - 1, alpha, beta, False, nodes)
            board.pop()
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = math.inf
        for move in _chess_order_moves(board):
            board.push(move)
            eval_score, _ = _chess_minimax(
                board, depth - 1, alpha, beta, True, nodes)
            board.pop()
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval, best_move


def _chess_best_move(board: chess.Board, max_depth: int = 2):
    # Adaptive depth: deeper in endgames, moderate in middlegame
    white_material = sum(_chess_piece_value(pt) * len(board.pieces(pt, chess.WHITE))
                         for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN])
    black_material = sum(_chess_piece_value(pt) * len(board.pieces(pt, chess.BLACK))
                         for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN])
    total_material = white_material + black_material
    adaptive = max_depth
    if total_material < 1200:  # endgame
        adaptive = max(max_depth, 4)
    elif total_material < 1800:  # late middlegame
        adaptive = max(max_depth, 3)
    maximizing = (board.turn == chess.WHITE)
    nodes = {'count': 0}
    _, move = _chess_minimax(board, adaptive, -
                             math.inf, math.inf, maximizing, nodes)
    if move is None:
        legal = list(board.legal_moves)
        return legal[0] if legal else None
    return move


@bp.route('/api/room/<int:room_id>/state')
@login_required
def get_room_state(room_id):
    room = GameRoom.query.get_or_404(room_id)
    data = room.to_dict()

    # Include messages for games that allow chat (e.g., chess)
    if room.game_type != 'trix':
        messages = room.messages.order_by(
            GameChat.created_at.asc()).limit(50).all()
        data['messages'] = [m.to_dict() for m in messages]

    # Solo game enhancements: drive bot turns and expose bot players
    try:
        if room.game_type == 'chess' and room.game_state and room.game_state.get(
                'is_solo'):
            state = room.game_state
            if state.get('engine') != 'client_stockfish':
                current_fen = state.get('fen', chess.STARTING_FEN)
                if current_fen == 'start':
                    current_fen = chess.STARTING_FEN
                board = chess.Board(current_fen)
                player = GamePlayer.query.filter_by(
                    room_id=room.id, user_id=current_user.id).first()
                is_white = True
                if player:
                    is_white = (player.seat_index == 0)
                bot_turn = (
                    board.turn == chess.BLACK and is_white) or (
                    board.turn == chess.WHITE and not is_white)

                if bot_turn and not board.is_game_over():
                    # Lock room to safely execute bot move
                    try:
                        locked_room = db.session.query(GameRoom).filter_by(
                            id=room.id).with_for_update().first()
                        if locked_room:
                            # Re-verify state after lock
                            state = locked_room.game_state
                            current_fen = state.get('fen', chess.STARTING_FEN)
                            if current_fen == 'start':
                                current_fen = chess.STARTING_FEN
                            board = chess.Board(current_fen)

                            # Double check it is still bot turn
                            bot_turn_still = (
                                board.turn == chess.BLACK and is_white) or (
                                board.turn == chess.WHITE and not is_white)

                            if bot_turn_still and not board.is_game_over():
                                bot_move = _chess_best_move(board, max_depth=3)
                                if bot_move:
                                    board.push(bot_move)
                                    state['fen'] = board.fen()
                                    state['turn'] = 'w' if board.turn == chess.WHITE else 'b'
                                    hist = state.get('history', [])
                                    hist.append(bot_move.uci())
                                    state['history'] = hist
                                    locked_room.game_state = state
                                    flag_modified(locked_room, 'game_state')
                                    db.session.commit()

                                    # Update response data
                                    data['game_state'] = state
                                    if socketio:
                                        payload = locked_room.to_dict()
                                        payload['game_state'] = state
                                        socketio.emit(
                                            'room_update', payload, room=f'room-{room.id}')
                    except Exception as e:
                        current_app.logger.error(
                            f"Error in chess bot move: {e}")
                        # Don't fail the request, just skip the move
                        pass
        if room.game_type in ['trix', 'tarneeb'] and room.game_state:
            state = room.game_state
            try:
                current_app.logger.info(
                    f"[STATE] Room {room.id} {room.game_type} phase={state.get('phase')} "
                    f"turn={state.get('turn_seat')} bidder={state.get('current_bid', {}).get('bidder')} "
                    f"passes={state.get('passes_in_row')}")
            except Exception:
                pass

            player = GamePlayer.query.filter_by(
                room_id=room.id, user_id=current_user.id).first()

            if state.get('is_solo') or len(state.get('bot_seats', [])) > 0:
                existing = {p['seat_index'] for p in data['players']}
                for seat in state.get('bot_seats', [1, 2, 3]):
                    if seat not in existing:
                        data['players'].append({
                            'user_id': 0,
                            'username': f'Bot P{seat + 1}',
                            'avatar': None,
                            'seat_index': seat,
                            'is_ready': True
                        })

                if room.game_type == 'tarneeb' and state.get(
                        'phase') == 'bidding':
                    if not state.get('current_bid', {}).get('bidder'):
                        turn = state.get('turn_seat', 0)
                        if turn != 0:
                            try:
                                hand = state.get(
                                    'hands', [[] for _ in range(4)])[turn]
                                suit_counts = {
                                    s: 0 for s in TarneebGameLogic.SUITS}
                                for c in hand:
                                    suit_counts[c['suit']] += 1
                                best_suit = max(
                                    suit_counts, key=lambda s: suit_counts[s])
                                state['current_bid'] = {
                                    'value': 7, 'trump': best_suit, 'bidder': turn}
                                state['bidding_history'] = state.get(
                                    'bidding_history', [])
                                state['bidding_history'].append(
                                    {'player': turn, 'action': 'bid', 'value': 7, 'trump': best_suit})
                                state['passes_in_row'] = 0
                                state['turn_seat'] = (turn + 1) % 4
                            except Exception:
                                pass

                if player and player.seat_index == 0:
                    steps = 0
                    while steps < 8:
                        steps += 1

                        if room.game_type == 'trix':
                            if state.get('phase') == 'choose_contract':
                                king = state.get('kingdom_player', 0)
                                if king == 0:
                                    break
                                import random
                                available = state.get(
                                    'available_contracts', [])
                                if not available:
                                    break
                                contract = random.choice(available)
                                res = TrixGameLogic.start_contract(
                                    state, contract)
                                if res.get('valid'):
                                    state = res['state']
                                    continue
                                break

                            if state.get('phase') == 'playing':
                                turn = state.get('turn_seat', 0)
                                if turn == 0:
                                    break
                                bot_move = TrixGameLogic.get_bot_move(
                                    state, turn)
                                if bot_move and bot_move.get('type') == 'play':
                                    res = TrixGameLogic.play_card(
                                        state, turn, bot_move['card'])
                                    if res.get('valid'):
                                        state = res['state']
                                        continue
                                break

                            break

                        if room.game_type == 'tarneeb':
                            phase = state.get('phase')
                            turn = state.get('turn_seat', 0)
                            if turn == 0:
                                break
                            action = TarneebGameLogic.get_bot_action(
                                state, turn)

                            if phase == 'bidding':
                                if action.get('type') in ['bid', 'pass']:
                                    res = TarneebGameLogic.make_bid(
                                        state, turn, action.get('bid'))
                                    if res.get('valid'):
                                        state = res['state']
                                        continue
                                break

                            if phase == 'doubling':
                                if action.get('type') == 'doubling':
                                    res = TarneebGameLogic.handle_doubling(
                                        state, turn, action.get('doubling'))
                                    if res.get('valid'):
                                        state = res['state']
                                        continue
                                break

                            if phase == 'playing':
                                if action.get('type') == 'play':
                                    res = TarneebGameLogic.play_card(
                                        state, turn, action.get('card'))
                                    if res.get('valid'):
                                        state = res['state']
                                        continue
                                break

                            break

                        break

                room.game_state = state

                # Check for finish
                if state.get(
                        'phase') == 'finished' and room.status != 'finished':
                    room.status = 'finished'
                    _distribute_prizes(room)

                flag_modified(room, 'game_state')
                db.session.commit()
                data['game_state'] = state
                if socketio:
                    payload = room.to_dict()
                    payload['game_state'] = state
                    socketio.emit('room_update', payload,
                                  room=f'room-{room.id}')
    except Exception as e:
        # Fail-safe: do not break state endpoint on bot errors
        current_app.logger.error(f"Solo bot progression error: {e}")

    return jsonify(data)


@bp.route('/api/room/<int:room_id>/chat', methods=['POST'])
@login_required
def send_chat(room_id):
    room = GameRoom.query.get_or_404(room_id)

    if room.game_type == 'trix':
        return jsonify({'error': 'Chat disabled for this game'}), 403

    msg = request.json.get('message')
    if msg:
        chat = GameChat(room_id=room.id, user_id=current_user.id, message=msg)
        db.session.add(chat)
        db.session.commit()
    return jsonify({'status': 'ok'})


@bp.route('/api/room/<int:room_id>/ready', methods=['POST'])
@login_required
def toggle_ready(room_id):
    # Lock room to sync player ready states and prevent race conditions
    try:
        room = db.session.query(GameRoom).filter_by(
            id=room_id).with_for_update().first()
    except Exception:
        room = GameRoom.query.get_or_404(room_id)

    if not room:
        abort(404)

    player = GamePlayer.query.filter_by(
        room_id=room.id, user_id=current_user.id).first_or_404()
    player.is_ready = not player.is_ready
    # Don't commit yet

    # Check if all ready to start
    players = room.players.all()
    max_players = 2 if room.game_type == 'chess' else 4

    if len(players) == max_players and all(p.is_ready for p in players):
        room.status = 'playing'
        # Initialize game state for Trix multiplayer when starting
        if room.game_type == 'trix':
            state = room.game_state or {}
            TrixGameLogic.init_game(state)
            TrixGameLogic.deal(state)
            style = state.get('trix_style', 'kingdoms')
            if style == 'complex':
                state['current_contract'] = 'complex'
                state['phase'] = 'playing'
            else:
                state['phase'] = 'choose_contract'
            room.game_state = state
        elif room.game_type == 'tarneeb':
            state = room.game_state or {}
            TarneebGameLogic.init_game(state)
            TarneebGameLogic.deal(state)
            room.game_state = state
            flag_modified(room, 'game_state')

    db.session.commit()

    return jsonify({'status': 'ok'})


@bp.route('/api/room/<int:room_id>/start', methods=['POST'])
@login_required
def start_room(room_id):
    # Lock room to prevent race conditions
    try:
        room = db.session.query(GameRoom).filter_by(
            id=room_id).with_for_update().first()
    except Exception:
        room = GameRoom.query.get_or_404(room_id)

    if not room:
        abort(404)

    player = GamePlayer.query.filter_by(
        room_id=room.id, user_id=current_user.id).first()
    if not player or player.seat_index != 0:
        return jsonify({'error': 'Not authorized'}), 403
    missing_bots = 0
    if room.status != 'playing':
        room.status = 'playing'
        state = room.game_state or {}

        # Check for missing players and fill with bots if necessary (Hybrid
        # Mode)
        players_count = room.players.count()

        if room.game_type == 'trix':
            if players_count < 4:
                existing_seats = [p.seat_index for p in room.players.all()]
                missing_seats = [
                    i for i in range(4) if i not in existing_seats]
                state['bot_seats'] = missing_seats
                state['is_solo'] = True  # Enable bot driver
                missing_bots = len(missing_seats)

            TrixGameLogic.init_game(state)
            TrixGameLogic.deal(state)
            style = state.get('trix_style', 'kingdoms')
            if style == 'complex':
                state['current_contract'] = 'complex'
                state['phase'] = 'playing'
            else:
                state['phase'] = 'choose_contract'
            room.game_state = state
            flag_modified(room, 'game_state')

        elif room.game_type == 'tarneeb':
            if players_count < 4:
                existing_seats = [p.seat_index for p in room.players.all()]
                missing_seats = [
                    i for i in range(4) if i not in existing_seats]
                state['bot_seats'] = missing_seats
                state['is_solo'] = True  # Enable bot driver
                missing_bots = len(missing_seats)

            TarneebGameLogic.init_game(state)
            TarneebGameLogic.deal(state)
            room.game_state = state
            flag_modified(room, 'game_state')

        elif room.game_type == 'chess':
            room.game_state = {
                'fen': chess.STARTING_FEN,
                'history': [],
                'turn': 'w'}

    # Bot Pot Contribution (System matches stake for bots)
    if missing_bots > 0 and room.stake_amount > 0:
        room.pot_amount += (missing_bots * room.stake_amount)

    db.session.commit()
    if socketio:
        payload = room.to_dict()
        socketio.emit('room_update', payload, room=f'room-{room.id}')
    return jsonify({'status': 'ok'})


@bp.route('/api/room/<int:room_id>/finish', methods=['POST'])
@login_required
def finish_room(room_id):
    try:
        room = db.session.query(GameRoom).filter_by(
            id=room_id).with_for_update().first()
    except Exception:
        room = GameRoom.query.get_or_404(room_id)
    if not room:
        abort(404)

    player = GamePlayer.query.filter_by(
        room_id=room.id, user_id=current_user.id).first()
    if not player or player.seat_index != 0:
        return jsonify({'error': 'Not authorized'}), 403
    room.status = 'finished'
    if room.game_state:
        try:
            state = room.game_state
            state['phase'] = 'finished'
            room.game_state = state
        except Exception:
            pass
    db.session.commit()
    if socketio:
        payload = room.to_dict()
        socketio.emit('room_update', payload, room=f'room-{room.id}')
    return jsonify({'status': 'ok'})


@bp.route('/api/room/<int:room_id>/delete', methods=['POST'])
@login_required
def delete_room(room_id):
    # Lock room to prevent race conditions during refund
    try:
        room = db.session.query(GameRoom).filter_by(
            id=room_id).with_for_update().first()
    except Exception:
        room = GameRoom.query.get(room_id)

    if not room:
        abort(404)

    player = GamePlayer.query.filter_by(
        room_id=room.id, user_id=current_user.id).first()
    if not player or player.seat_index != 0:
        return jsonify({'error': 'Not authorized'}), 403

    # Refund all players if stake exists and game not finished
    if room.status != 'finished' and room.stake_amount > 0:
        players = room.players.all()
        for p in players:
            # Lock User to update balance safely
            try:
                u = db.session.query(User).filter_by(
                    id=p.user_id).with_for_update().first()
            except Exception:
                u = User.query.get(p.user_id)

            if u:
                if room.currency_type == 'money':
                    ResourceService.modify_resources(p.user_id,
                                                     {'money': room.stake_amount},
                                                     'room_delete_refund',
                                                     auto_commit=False,
                                                     expected_version=None)
                else:
                    ResourceService.modify_resources(p.user_id,
                                                     {'diamonds': room.stake_amount},
                                                     'room_delete_refund',
                                                     auto_commit=False,
                                                     expected_version=None)

    db.session.delete(room)

    # Log room deletion
    log = UserLog(
        user_id=current_user.id,
        action='ROOM_DELETE_META',
        details=json.dumps({
            'room_id': room.id,
            'room_name': room.name,
            'game_type': room.game_type,
            'stake_amount': room.stake_amount,
            'currency_type': room.currency_type,
            'status': room.status,
            'refunded_players': len(players)
        }),
        result='success',
        ip_address=request.remote_addr,
        user_agent=str(request.user_agent)
    )
    db.session.add(log)

    db.session.commit()
    if socketio:
        try:
            socketio.emit(
                'room_update', {
                    'deleted': True, 'room_id': room_id}, room=f'room-{room_id}')
        except Exception:
            pass
    return jsonify({'status': 'ok'})


@bp.route('/api/room/<int:room_id>/leave', methods=['POST'])
@login_required
def leave_game(room_id):
    # Lock room to prevent race conditions (e.g. concurrent finish/delete)
    try:
        room = db.session.query(GameRoom).filter_by(
            id=room_id).with_for_update().first()
    except Exception:
        room = GameRoom.query.get(room_id)

    if not room:
        abort(404)

    player = GamePlayer.query.filter_by(
        room_id=room.id, user_id=current_user.id).first()

    if not player:
        return jsonify({'error': 'Not in room'}), 404

    if room.status == 'playing':
        # Forfeit logic
        if room.game_type == 'chess':
            # Resign: Opponent wins
            state = room.game_state
            if player.seat_index == 0:  # White left
                state['result'] = '0-1'  # Black wins
            else:  # Black left
                state['result'] = '1-0'  # White wins

            state['status'] = 'finished'
            room.game_state = state
            room.status = 'finished'
            _distribute_prizes(room)
            db.session.commit()

            # Remove player from room (optional, but good for cleanup)
            # Actually, in Chess, we keep them to show the result.
            # But the user request implies they "lose the bet".
            # Logic handled in _distribute_prizes using 'result'.

        else:
            # Multiplayer (Trix/Tarneeb)
            # Remove player -> Replaced by bot -> Loses claim to pot
            seat = player.seat_index
            db.session.delete(player)

            # Update state to include bot
            if room.game_state:
                # Copy to ensure change detection
                state = dict(room.game_state)
                if 'bot_seats' not in state:
                    state['bot_seats'] = []
                if seat not in state['bot_seats']:
                    state['bot_seats'].append(seat)
                state['is_solo'] = True  # Enable bot driver
                room.game_state = state

            db.session.commit()

            # Notify room to refresh state (which will pick up missing seat as
            # bot)
            if socketio:
                payload = room.to_dict()
                socketio.emit('room_update', payload, room=f'room-{room.id}')

        return jsonify({'status': 'ok', 'message': 'Forfeited'})

    else:
        # Lobby leave (refund logic usually applies here if we implemented it,
        # but for now just leave)
        # If there was a stake, we should refund if game hasn't started.
        if room.stake_amount > 0:
            if room.currency_type == 'money':
                ResourceService.modify_resources(
                    current_user.id, {
                        'money': room.stake_amount}, 'room_leave_refund', auto_commit=False, expected_version=None)
            else:
                ResourceService.modify_resources(
                    current_user.id, {
                        'diamonds': room.stake_amount}, 'room_leave_refund', auto_commit=False, expected_version=None)
            room.pot_amount -= room.stake_amount

        db.session.delete(player)

        # Log room leave
        log = UserLog(
            user_id=current_user.id,
            action='ROOM_LEAVE_META',
            details=json.dumps({
                'room_id': room.id,
                'room_name': room.name,
                'game_type': room.game_type,
                'stake_amount': room.stake_amount,
                'currency_type': room.currency_type,
                'status': room.status,
                'refunded': room.stake_amount > 0,
                'seat_index': player.seat_index if player else None
            }),
            result='success',
            ip_address=request.remote_addr,
            user_agent=str(request.user_agent)
        )
        db.session.add(log)

        db.session.commit()

        if socketio:
            payload = room.to_dict()
            socketio.emit('room_update', payload, room=f'room-{room.id}')

        return jsonify({'status': 'ok', 'message': 'Left room'})


@bp.route('/api/room/<int:room_id>/events')
@login_required
def room_events(room_id):
    def event_stream():
        for i in range(300):
            room = GameRoom.query.get(room_id)
            if not room:
                yield "event:close\ndata: {}\n\n"
                break
            payload = room.to_dict()
            # Enrich players for solo games with bot seats and drive bot turns
            # lightly
            if room.game_state and room.game_state.get(
                    'is_solo') and room.game_type in ['trix', 'tarneeb']:
                state = room.game_state
                existing = {p['seat_index'] for p in payload['players']}
                for seat in state.get('bot_seats', [1, 2, 3]):
                    if seat not in existing:
                        payload['players'].append({
                            'user_id': 0,
                            'username': f'Bot P{seat + 1}',
                            'avatar': None,
                            'seat_index': seat,
                            'is_ready': True
                        })
                # Advance bot logic lightly to keep real-time responsiveness
                steps = 0
                while steps < 4:
                    steps += 1
                    if room.game_type == 'trix' and state.get(
                            'phase') == 'choose_contract':
                        king = state.get('kingdom_player', 0)
                        if king != 0:
                            import random
                            available = state.get('available_contracts', [])
                            if not available:
                                break
                            contract = random.choice(available)
                            res = TrixGameLogic.start_contract(state, contract)
                            if res.get('valid'):
                                state = res['state']
                                continue
                            else:
                                break
                        else:
                            break
                    elif room.game_type == 'trix' and state.get('phase') == 'playing':
                        turn = state.get('turn_seat', 0)
                        if turn != 0:
                            bot_move = TrixGameLogic.get_bot_move(state, turn)
                            if bot_move and bot_move.get('type') == 'play':
                                res = TrixGameLogic.play_card(
                                    state, turn, bot_move['card'])
                                if res.get('valid'):
                                    state = res['state']
                                    continue
                                else:
                                    break
                            else:
                                break
                        else:
                            break
                    elif room.game_type == 'tarneeb':
                        if state.get('phase') == 'bidding':
                            turn = state.get('turn_seat', 0)
                            if turn != 0:
                                action = TarneebGameLogic.get_bot_action(
                                    state, turn)
                                if action['type'] == 'bid' or action['type'] == 'pass':
                                    res = TarneebGameLogic.make_bid(
                                        state, turn, action['bid'])
                                    if res.get('valid'):
                                        state = res['state']
                                        continue
                                    else:
                                        break
                                else:
                                    break
                            else:
                                break
                        elif state.get('phase') == 'doubling':
                            turn = state.get('turn_seat', 0)
                            if turn != 0:
                                action = TarneebGameLogic.get_bot_action(
                                    state, turn)
                                if action['type'] == 'doubling':
                                    res = TarneebGameLogic.handle_doubling(
                                        state, turn, action['doubling'])
                                    if res.get('valid'):
                                        state = res['state']
                                        continue
                                    else:
                                        break
                                else:
                                    break
                            else:
                                break
                        elif state.get('phase') == 'playing':
                            turn = state.get('turn_seat', 0)
                            if turn != 0:
                                action = TarneebGameLogic.get_bot_action(
                                    state, turn)
                                if action['type'] == 'play':
                                    res = TarneebGameLogic.play_card(
                                        state, turn, action['card'])
                                    if res.get('valid'):
                                        state = res['state']
                                        continue
                                    else:
                                        break
                                else:
                                    break
                            else:
                                break
                    else:
                        break
                # Persist and expose new state
                room.game_state = state
                db.session.commit()
                payload['game_state'] = state
                if socketio:
                    socketio.emit('room_update', payload,
                                  room=f'room-{room.id}')
            else:
                # Non-trix: include messages
                messages = room.messages.order_by(
                    GameChat.created_at.asc()).limit(50).all()
                payload['messages'] = [m.to_dict() for m in messages]
            payload['timestamp'] = int(time.time() * 1000)
            try:
                yield f"data: {json.dumps(payload)}\n\n"
                time.sleep(1)
            except GeneratorExit:
                break
            except Exception as e:
                current_app.logger.error(f"SSE stream error: {e}")
                time.sleep(1)
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return Response(
        stream_with_context(
            event_stream()),
        mimetype='text/event-stream',
        headers=headers)


@bp.route('/api/room/<int:room_id>/move', methods=['POST'])
@login_required
def make_move(room_id):
    print(f"[DEBUG] make_move called for room {room_id}")
    # Lock room to prevent race conditions on game state
    try:
        room = db.session.query(GameRoom).filter_by(
            id=room_id).with_for_update().first()
    except Exception:
        room = GameRoom.query.get_or_404(room_id)

    if not room:
        abort(404)

    data = request.json
    print(f"[DEBUG] make_move data: {data}, game_type: {repr(room.game_type)}")
    print(f"[DEBUG] Is tarneeb? {room.game_type == 'tarneeb'}")

    # Basic validation could go here
    current_state = room.game_state or {}

    if room.game_type == 'chess':
        # Server-side validation with python-chess
        current_fen = current_state.get('fen', chess.STARTING_FEN)
        if current_fen == 'start':
            current_fen = chess.STARTING_FEN
        board = chess.Board(current_fen)

        action = data.get('action')
        move_uci = data.get('move')  # Expecting UCI string e.g. "e2e4"

        if action == 'set_engine':
            eng = data.get('engine')
            if eng not in ['minimax', 'client_stockfish']:
                return jsonify({'error': 'Invalid engine'}), 400
            # Only solo rooms support engine toggle
            if not current_state.get('is_solo'):
                return jsonify(
                    {'error': 'Engine toggle only in solo mode'}), 400
            current_state['engine'] = eng

        elif action == 'engine_move':
            # Accept bestmove from client Stockfish when it's bot's turn
            if not current_state.get('is_solo'):
                return jsonify({'error': 'Not solo mode'}), 400
            if current_state.get('engine') != 'client_stockfish':
                return jsonify(
                    {'error': 'Engine not set to client_stockfish'}), 400
            try:
                move = chess.Move.from_uci(move_uci or '')
            except ValueError:
                return jsonify({'error': 'Invalid move format'}), 400
            # Ensure it's not the human's turn (human is seat_index 0 -> white)
            human_is_white = True
            if (board.turn == chess.WHITE and human_is_white) or (
                    board.turn == chess.BLACK and not human_is_white):
                return jsonify(
                    {'error': 'Engine cannot move on human turn'}), 403
            if move in board.legal_moves:
                board.push(move)
                current_state['fen'] = board.fen()
                current_state['turn'] = 'w' if board.turn == chess.WHITE else 'b'
                history = current_state.get('history', [])
                history.append(move.uci())
                current_state['history'] = history
                if board.is_game_over():
                    current_state['status'] = 'finished'
                    current_state['result'] = board.result()
                    room.status = 'finished'
                    _distribute_prizes(room)
            else:
                return jsonify({'error': 'Illegal engine move'}), 400

        elif not move_uci:
            # Fallback for old clients or reset
            if data.get('fen') == 'start':
                current_state = {'fen': 'start', 'history': [], 'turn': 'w'}
            else:
                return jsonify({'error': 'No move provided'}), 400
        else:
            try:
                move = chess.Move.from_uci(move_uci)

                # Check if it's the correct player's turn
                player = GamePlayer.query.filter_by(
                    room_id=room.id, user_id=current_user.id).first()
                if not player:
                    return jsonify({'error': 'Player not in room'}), 403

                is_white = (player.seat_index == 0)
                if (board.turn == chess.WHITE and not is_white) or (
                        board.turn == chess.BLACK and is_white):
                    return jsonify({'error': 'Not your turn'}), 403

                if move in board.legal_moves:
                    board.push(move)
                    current_state['fen'] = board.fen()
                    # current_state['turn'] is derived from FEN, but we can
                    # keep explicit track if needed
                    current_state['turn'] = 'w' if board.turn == chess.WHITE else 'b'

                    history = current_state.get('history', [])
                    history.append(move_uci)
                    current_state['history'] = history

                    if board.is_game_over():
                        current_state['status'] = 'finished'
                        current_state['result'] = board.result()
                        room.status = 'finished'
                        _distribute_prizes(room)

                    # Handle Bot if solo
                    elif current_state.get('is_solo'):
                        if current_state.get('engine') == 'client_stockfish':
                            pass
                        else:
                            bot_move = _chess_best_move(board, max_depth=3)
                            if bot_move:
                                board.push(bot_move)
                                current_state['fen'] = board.fen()
                                current_state['turn'] = 'w' if board.turn == chess.WHITE else 'b'

                                history = current_state.get('history', [])
                                history.append(bot_move.uci())
                                current_state['history'] = history

                                if board.is_game_over():
                                    current_state['status'] = 'finished'
                                    current_state['result'] = board.result()
                                    room.status = 'finished'
                                    _distribute_prizes(room)
                else:
                    return jsonify({'error': 'Illegal move'}), 400
            except ValueError:
                return jsonify({'error': 'Invalid move format'}), 400

    elif room.game_type == 'trix':
        # Trix logic update with validation
        action = data.get('action')

        player = GamePlayer.query.filter_by(
            room_id=room.id, user_id=current_user.id).first()
        if not player:
            return jsonify({'error': 'Player not found'}), 403

        # Defensive: ensure required keys exist to avoid KeyErrors in logic
        if 'doubles' not in current_state:
            current_state['doubles'] = {'king': None, 'queens': {}}
        if 'doubling_confirms' not in current_state:
            current_state['doubling_confirms'] = []
        if 'trix_piles' not in current_state:
            from routes.trix_logic import TrixGameLogic as _TL
            current_state['trix_piles'] = {s: [] for s in _TL.SUITS}

        if action == 'choose_contract':
            if current_state['phase'] != 'choose_contract':
                return jsonify(
                    {'error': 'Not in contract selection phase'}), 400

            if current_state['kingdom_player'] != player.seat_index:
                return jsonify(
                    {'error': 'Not your turn to choose contract'}), 403

            result = TrixGameLogic.start_contract(
                current_state, data.get('contract'))
            if not result.get('valid'):
                return jsonify({'error': result.get('message')}), 400

            current_state = result['state']

        elif action == 'double':
            dtype = data.get('type')
            suit = data.get('suit')
            try:
                result = TrixGameLogic.declare_double(
                    current_state, player.seat_index, dtype, suit)
                if not result.get('valid'):
                    return jsonify({'error': result.get('message')}), 400
                current_state = result['state']
            except Exception as e:
                current_app.logger.exception(f"Trix declare_double error: {e}")
                return jsonify({'error': 'Server error during double'}), 500

        elif action == 'confirm_doubling':
            try:
                result = TrixGameLogic.confirm_doubling(
                    current_state, player.seat_index)
                if not result.get('valid'):
                    return jsonify({'error': result.get('message')}), 400
                current_state = result['state']
            except Exception as e:
                current_app.logger.exception(
                    f"Trix confirm_doubling error: {e}")
                return jsonify({'error': 'Server error during confirm'}), 500

        elif action == 'play_card':
            current_app.logger.debug(
                f"Trix Play Card Request seat={player.seat_index} card={data.get('card')}")
            try:
                result = TrixGameLogic.play_card(
                    current_state, player.seat_index, data.get('card'))
                current_app.logger.debug(
                    f"Trix Play Card Result valid={result.get('valid')} msg={result.get('message')}")

                if not result.get('valid'):
                    return jsonify({'error': result.get('message')}), 400

                current_state = result['state']
            except Exception as e:
                current_app.logger.exception(f"Trix play_card error: {e}")
                return jsonify({'error': 'Server error during play'}), 500

            if current_state.get('phase') == 'finished':
                room.status = 'finished'
                _distribute_prizes(room)

        if current_state.get('is_solo') or len(
                current_state.get('bot_seats', [])) > 0:
            try:
                loop_safety = 0
                while True:
                    loop_safety += 1
                    if loop_safety > 100:
                        current_app.logger.warning(
                            f"Trix bot loop limit reached for room {room.id}")
                        break
                    if current_state['phase'] == 'choose_contract':
                        king_seat = current_state['kingdom_player']
                        if king_seat != 0:
                            import random
                            available = current_state.get(
                                'available_contracts', [])
                            if available:
                                contract = random.choice(available)
                                res = TrixGameLogic.start_contract(
                                    current_state, contract)
                                if res.get('valid'):
                                    current_state = res['state']
                                    continue
                            else:
                                break
                        else:
                            break
                    elif current_state['phase'] == 'doubling':
                        bot_indices = [i for i in [0, 1, 2, 3] if i != 0]
                        if len(current_state.get('bot_seats', [])) > 0:
                            bot_indices = current_state['bot_seats']
                        action_taken = False
                        for b in bot_indices:
                            bot_move = TrixGameLogic.get_bot_move(
                                current_state, b)
                            if bot_move:
                                res = None
                                if bot_move['type'] == 'confirm_doubling':
                                    res = TrixGameLogic.confirm_doubling(
                                        current_state, b)
                                elif bot_move['type'] == 'double':
                                    res = TrixGameLogic.declare_double(
                                        current_state, b, bot_move['item'], bot_move.get('suit'))
                                if res and res.get('valid'):
                                    current_state = res['state']
                                    action_taken = True
                        if not action_taken:
                            break
                    elif current_state['phase'] == 'playing':
                        if current_state['turn_seat'] != 0:
                            bot_seat = current_state['turn_seat']
                            bot_move = TrixGameLogic.get_bot_move(
                                current_state, bot_seat)
                            if bot_move and bot_move.get('type') == 'play':
                                res = TrixGameLogic.play_card(
                                    current_state, bot_seat, bot_move['card'])
                                if res.get('valid'):
                                    current_state = res['state']
                                    if current_state.get(
                                            'phase') == 'finished':
                                        room.status = 'finished'
                                        _distribute_prizes(room)
                                        break
                                else:
                                    break
                            else:
                                break
                        else:
                            break
                    if current_state.get('phase') not in [
                            'choose_contract', 'playing', 'doubling']:
                        break
            except Exception as e:
                current_app.logger.exception(f"Trix bot loop error: {e}")

    elif room.game_type == 'tarneeb':
        action = data.get('action')
        print(f"[DEBUG] Inside Tarneeb block. Action: {action}")
        player = GamePlayer.query.filter_by(
            room_id=room.id, user_id=current_user.id).first()
        if not player:
            return jsonify({'error': 'Player not found'}), 403
        if action == 'bid':
            try:
                res = TarneebGameLogic.make_bid(
                    current_state, player.seat_index, data.get('bid', {}))
                if not res.get('valid'):
                    return jsonify({'error': res.get('message')}), 400
                current_state = res['state']
                # Safety nudge: if human passed and bots haven't started, seed
                # minimal bid
                if current_state.get('phase') == 'bidding':
                    if not current_state.get('current_bid', {}).get('bidder'):
                        turn = current_state.get('turn_seat', 0)
                        if turn != 0:
                            try:
                                hand = current_state.get(
                                    'hands', [[] for _ in range(4)])[turn]
                                suit_counts = {
                                    s: 0 for s in TarneebGameLogic.SUITS}
                                for c in hand:
                                    suit_counts[c['suit']] += 1
                                best_suit = max(
                                    suit_counts, key=lambda s: suit_counts[s])
                                current_state['current_bid'] = {
                                    'value': 7, 'trump': best_suit, 'bidder': turn}
                                hist = current_state.get('bidding_history', [])
                                hist.append(
                                    {'player': turn, 'action': 'bid', 'value': 7, 'trump': best_suit})
                                current_state['bidding_history'] = hist
                                current_state['passes_in_row'] = 0
                                current_state['turn_seat'] = (turn + 1) % 4
                            except Exception:
                                pass
            except Exception as e:
                current_app.logger.exception(f"Tarneeb bid error: {e}")
                return jsonify({'error': 'Server error during bid'}), 500
        elif action == 'doubling':
            try:
                res = TarneebGameLogic.handle_doubling(
                    current_state, player.seat_index, data.get('doubling', {}))
                if not res.get('valid'):
                    return jsonify({'error': res.get('message')}), 400
                current_state = res['state']
            except Exception as e:
                current_app.logger.exception(f"Tarneeb doubling error: {e}")
                return jsonify({'error': 'Server error during doubling'}), 500
        elif action == 'play_card':
            try:
                res = TarneebGameLogic.play_card(
                    current_state, player.seat_index, data.get('card'))
                if not res.get('valid'):
                    return jsonify({'error': res.get('message')}), 400
                current_state = res['state']
                if current_state.get('phase') == 'finished':
                    room.status = 'finished'
                    _distribute_prizes(room)
            except Exception as e:
                current_app.logger.exception(f"Tarneeb play error: {e}")
                return jsonify({'error': 'Server error during play'}), 500
        # Solo bot loop (drive bots even if just bot_seats present)
        if current_state.get('is_solo') or len(
                current_state.get('bot_seats', [])) > 0:
            print(
                f"[DEBUG] Entering bot loop. Phase: {current_state.get('phase')}, "
                f"Turn: {current_state.get('turn_seat')}")
            steps = 0
            while steps < 8:
                steps += 1
                if current_state.get('phase') == 'bidding':
                    turn = current_state.get('turn_seat', 0)
                    print(f"[DEBUG] Bot Loop Step {steps}: Turn {turn}")
                    if turn != 0:
                        action = TarneebGameLogic.get_bot_action(
                            current_state, turn)
                        print(f"[DEBUG] Bot {turn} action: {action}")
                        if action['type'] in ['bid', 'pass']:
                            res = TarneebGameLogic.make_bid(
                                current_state, turn, action['bid'])
                            if res.get('valid'):
                                current_state = res['state']
                                continue
                            else:
                                print(f"[DEBUG] Bot bid invalid: {res}")
                                break
                        else:
                            break
                    else:
                        print("[DEBUG] Turn is 0 (Human), exiting bot loop")
                        break
                elif current_state.get('phase') == 'doubling':
                    turn = current_state.get('turn_seat', 0)
                    if turn != 0:
                        action = TarneebGameLogic.get_bot_action(
                            current_state, turn)
                        if action['type'] == 'doubling':
                            res = TarneebGameLogic.handle_doubling(
                                current_state, turn, action['doubling'])
                            if res.get('valid'):
                                current_state = res['state']
                                continue
                            else:
                                break
                        else:
                            break
                    else:
                        break
                elif current_state.get('phase') == 'playing':
                    turn = current_state.get('turn_seat', 0)
                    if turn != 0:
                        action = TarneebGameLogic.get_bot_action(
                            current_state, turn)
                        if action['type'] == 'play':
                            res = TarneebGameLogic.play_card(
                                current_state, turn, action['card'])
                            if res.get('valid'):
                                current_state = res['state']
                                if current_state.get('phase') == 'finished':
                                    room.status = 'finished'
                                    _distribute_prizes(room)
                                    break
                                continue
                            else:
                                break
                        else:
                            break
                    else:
                        break
                else:
                    break
    room.game_state = current_state
    flag_modified(room, 'game_state')
    db.session.commit()
    if socketio:
        payload = room.to_dict()
        payload['game_state'] = current_state
        socketio.emit('room_update', payload, room=f'room-{room.id}')
    return jsonify({'status': 'ok', 'state': current_state})

# Solo Routes (Offline / vs Computer)


@bp.route('/chess/solo')
@login_required
def chess_solo():
    # Create solo chess room
    room = GameRoom(
        game_type='chess',
        name=f"{current_user.username}'s Solo Game",
        status='playing')
    room.game_state = {
        'fen': chess.STARTING_FEN,
        'history': [],
        'turn': 'w',
        'is_solo': True}

    db.session.add(room)
    db.session.commit()

    player = GamePlayer(
        room_id=room.id,
        user_id=current_user.id,
        seat_index=0,
        is_ready=True)
    db.session.add(player)
    db.session.commit()

    return redirect(url_for('entertainment.room', room_id=room.id))


@bp.route('/trix/solo')
@login_required
def trix():
    # Create solo trix room
    room = GameRoom(
        game_type='trix',
        name=f"{current_user.username}'s Solo Game",
        status='playing')
    room.game_state = {'is_solo': True, 'bot_seats': [1, 2, 3]}
    TrixGameLogic.init_game(room.game_state)
    # Explicitly set phase to choose_contract so user can pick
    room.game_state['phase'] = 'choose_contract'

    db.session.add(room)
    db.session.commit()

    player = GamePlayer(
        room_id=room.id,
        user_id=current_user.id,
        seat_index=0,
        is_ready=True)
    db.session.add(player)
    db.session.commit()

    return redirect(url_for('entertainment.room', room_id=room.id))


if socketio:
    @socketio.on('subscribe')
    def _subscribe(data):
        room_key = data.get('room') or f"room-{data.get('room_id')}"
        if room_key:
            join_room(room_key)

    @socketio.on('unsubscribe')
    def _unsubscribe(data):
        room_key = data.get('room') or f"room-{data.get('room_id')}"
        if room_key:
            leave_room(room_key)
