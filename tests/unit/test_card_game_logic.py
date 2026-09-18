from routes.tarneeb_logic import TarneebGameLogic
from routes.trix_logic import TrixGameLogic


def test_tarneeb_deal_produces_four_complete_hands():
    state = {}
    TarneebGameLogic.init_game(state)
    result = TarneebGameLogic.deal(state)

    assert result['valid'] is True
    assert [len(hand) for hand in state['hands']] == [13, 13, 13, 13]
    assert len({(card['suit'], card['rank']) for hand in state['hands'] for card in hand}) == 52
    assert state['phase'] == 'bidding'


def test_tarneeb_rejects_invalid_and_out_of_turn_bids():
    state = {}
    TarneebGameLogic.init_game(state)
    TarneebGameLogic.deal(state)

    assert TarneebGameLogic.make_bid(state, 1, {'value': 7, 'trump': '♥'})['valid'] is False
    assert TarneebGameLogic.make_bid(state, 0, {'value': 6, 'trump': '♥'})['valid'] is False
    assert TarneebGameLogic.make_bid(state, 0, {'value': 7, 'trump': '♥'})['valid'] is True
    assert state['current_bid']['bidder'] == 0


def test_tarneeb_bidding_and_doubling_reach_playing_phase():
    state = {}
    TarneebGameLogic.init_game(state)
    TarneebGameLogic.deal(state)
    assert TarneebGameLogic.make_bid(state, 0, {'value': 7, 'trump': '♠'})['valid']

    for player in (1, 2, 3):
        assert TarneebGameLogic.make_bid(state, player, {'action': 'pass'})['valid']
    assert state['phase'] == 'doubling'
    assert TarneebGameLogic.handle_doubling(state, 1, {'action': 'pass'})['valid']
    assert TarneebGameLogic.handle_doubling(state, 3, {'action': 'pass'})['valid']
    assert state['phase'] == 'playing'
    assert state['turn_seat'] == 0


def test_tarneeb_play_card_enforces_turn_and_follow_suit():
    state = {}
    TarneebGameLogic.init_game(state)
    state.update({
        'phase': 'playing',
        'turn_seat': 0,
        'trump': '♠',
        'hands': [
            [{'suit': '♥', 'rank': '2'}, {'suit': '♠', 'rank': 'A'}],
            [{'suit': '♥', 'rank': '3'}],
            [],
            [],
        ],
        'trick': [],
        'tricks_won': [0, 0, 0, 0],
    })
    assert TarneebGameLogic.play_card(state, 1, {'suit': '♥', 'rank': '3'})['valid'] is False
    assert TarneebGameLogic.play_card(state, 0, {'suit': '♠', 'rank': 'A'})['valid'] is True
    assert state['turn_seat'] == 1


def test_trix_init_and_contract_lifecycle():
    state = {}
    TrixGameLogic.init_game(state)
    assert [len(hand) for hand in state['hands'].values()] == [13, 13, 13, 13]
    assert state['phase'] == 'choose_contract'
    assert TrixGameLogic.start_contract(state, 'not-a-contract')['valid'] is False
    assert TrixGameLogic.start_contract(state, 'king')['valid'] is True
    assert state['phase'] == 'doubling'
    for player in range(4):
        assert TrixGameLogic.confirm_doubling(state, player)['valid'] is True
    assert state['phase'] == 'playing'


def test_trix_play_card_rejects_wrong_turn_and_missing_card():
    state = {
        'phase': 'playing',
        'current_contract': 'king',
        'turn_seat': 0,
        'hands': {0: [{'suit': '♠', 'rank': 'A'}], 1: [], 2: [], 3: []},
        'trick': [],
        'hearts_broken': False,
    }
    card = {'suit': '♠', 'rank': 'A'}
    assert TrixGameLogic.play_card(state, 1, card)['valid'] is False
    assert TrixGameLogic.play_card(state, 0, {'suit': '♥', 'rank': '2'})['valid'] is False
    assert TrixGameLogic.play_card(state, 0, card)['valid'] is True
    assert state['hands'][0] == []


def test_tarneeb_four_pass_fallback_and_bot_actions():
    state = {}
    TarneebGameLogic.init_game(state)
    TarneebGameLogic.deal(state)
    for player in range(4):
        assert TarneebGameLogic.make_bid(state, player, {'action': 'pass'})['valid']
    assert state['current_bid']['value'] == 7
    assert state['current_bid']['bidder'] == 0

    state['phase'] = 'playing'
    state['turn_seat'] = 0
    state['trump'] = '♠'
    state['declarer_team'] = 'A'
    action = TarneebGameLogic.get_bot_action(state, 0)
    assert action['type'] == 'play'
    assert action['card'] in state['hands'][0]


def test_tarneeb_doubling_actions_and_trick_resolution():
    state = {}
    TarneebGameLogic.init_game(state)
    state.update({
        'phase': 'doubling',
        'turn_seat': 1,
        'current_bid': {'value': 7, 'trump': '♠', 'bidder': 0},
        'declarer_team': 'A',
    })
    assert TarneebGameLogic.handle_doubling(state, 1, {'action': 'double'})['valid']
    assert state['doubled'] is True
    assert TarneebGameLogic.handle_doubling(state, 0, {'action': 'redouble'})['valid']
    assert state['redoubled'] is True

    state.update({
        'phase': 'playing',
        'turn_seat': 0,
        'hands': [
            [{'suit': '♥', 'rank': 'A'}],
            [{'suit': '♥', 'rank': 'K'}],
            [{'suit': '♥', 'rank': '2'}],
            [{'suit': '♠', 'rank': 'A'}],
        ],
        'trick': [],
        'tricks_won': [0, 0, 0, 0],
        'team_tricks': {'A': 0, 'B': 0},
        'team_scores': {'A': 0, 'B': 0},
        'contract_value': 7,
    })
    for player, card in enumerate([
        {'suit': '♥', 'rank': 'A'},
        {'suit': '♥', 'rank': 'K'},
        {'suit': '♥', 'rank': '2'},
        {'suit': '♠', 'rank': 'A'},
    ]):
        assert TarneebGameLogic.play_card(state, player, card)['valid']
    assert state['tricks_won'][0] == 1
    assert state['turn_seat'] == 0


def test_trix_trick_scoring_and_follow_suit():
    state = {
        'phase': 'playing',
        'current_contract': 'king',
        'turn_seat': 0,
        'hands': {
            0: [{'suit': '♠', 'rank': 'A'}],
            1: [{'suit': '♠', 'rank': '2'}, {'suit': '♥', 'rank': 'K'}],
            2: [{'suit': '♠', 'rank': 'K'}],
            3: [{'suit': '♦', 'rank': '2'}],
        },
        'trick': [],
        'last_trick': [],
        'scores': {0: 0, 1: 0, 2: 0, 3: 0},
        'doubles': {'king': None, 'queens': {}},
        'trix_piles': {s: [] for s in TrixGameLogic.SUITS},
        'kingdom_player': 0,
        'available_contracts': ['king'],
        'trix_style': 'kingdoms',
        'kingdoms_played': 0,
    }
    assert TrixGameLogic.play_card(state, 0, {'suit': '♠', 'rank': 'A'})['valid']
    assert not TrixGameLogic.play_card(
        state, 1, {'suit': '♥', 'rank': 'K'})['valid']
    assert TrixGameLogic.play_card(state, 1, {'suit': '♠', 'rank': '2'})['valid']
    assert TrixGameLogic.play_card(state, 2, {'suit': '♠', 'rank': 'K'})['valid']
    assert TrixGameLogic.play_card(state, 3, {'suit': '♦', 'rank': '2'})['valid']
    assert state['scores'][0] == 0
    assert state['turn_seat'] == 0


def test_trix_sequence_moves_and_doubles():
    state = {
        'phase': 'playing',
        'current_contract': 'trix',
        'turn_seat': 0,
        'hands': {0: [{'suit': '♠', 'rank': 'J'}, {'suit': '♠', 'rank': 'Q'}],
                  1: [], 2: [], 3: []},
        'trix_piles': {s: [] for s in TrixGameLogic.SUITS},
        'finished_players': [], 'scores': {0: 0, 1: 0, 2: 0, 3: 0},
    }
    assert TrixGameLogic.play_card(state, 0, {'suit': '♠', 'rank': 'Q'})['valid'] is False
    assert TrixGameLogic.play_card(state, 0, {'suit': '♠', 'rank': 'J'})['valid']
    assert TrixGameLogic.play_card(state, 1, {'suit': '♠', 'rank': 'Q'})['valid'] is False

    state.update({'phase': 'doubling', 'current_contract': 'king',
                  'hands': {0: [{'suit': '♥', 'rank': 'K'}], 1: [], 2: [], 3: []},
                  'doubles': {'king': None, 'queens': {}}})
    assert TrixGameLogic.declare_double(state, 0, 'king')['valid']
    assert state['doubles']['king'] == 0
