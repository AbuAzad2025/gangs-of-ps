class TrixGame {
  constructor() {
    this.ui = null;
    this.turn = 0;
    this.contract = null;
    this.trick = [];
    this.round = 0;
    this.started = false;
    this.contracts = {
      king: { nameAr: 'شيخ الكبة', kind: 'king' },
      queens: { nameAr: 'بنات', kind: 'queens' },
      diamonds: { nameAr: 'ديناري', kind: 'diamonds' },
      slapping: { nameAr: 'لطوش', kind: 'slapping' },
      complex: { nameAr: 'كومبلكس', kind: 'complex' }
    };
    this.players = [
      { id: 0, name: 'You', hand: [], score: 0 },
      { id: 1, name: 'Bot 1', hand: [], score: 0 },
      { id: 2, name: 'Bot 2', hand: [], score: 0 },
      { id: 3, name: 'Bot 3', hand: [], score: 0 }
    ];
  }

  init(uiCallback) {
    this.ui = uiCallback;
    this._resetForNewRound();
    this._emit('showContractSelector', { player: this.players[0] });
    this._emitBoard();
  }

  selectContract(name) {
    if (!this.contracts[name]) {
      this._emit('message', 'عقد غير معروف.');
      return;
    }
    this.contract = name;
    this.started = true;
    this._emit('message', 'بدأت اللعبة.');
    this._emitBoard();
    this._advanceIfBotsTurn();
  }

  playCard(playerId, handIndex) {
    if (!this.started) return;
    if (playerId !== this.turn) return;
    const player = this.players[playerId];
    if (!player || !player.hand || handIndex < 0 || handIndex >= player.hand.length) return;

    const card = player.hand[handIndex];
    if (!this._isMoveLegal(playerId, card)) {
      this._emit('invalidMove', null);
      return;
    }

    player.hand.splice(handIndex, 1);
    this.trick.push({ player: playerId, card });
    this._emitBoard();

    if (this.trick.length === 4) {
      const winner = this._resolveTrickWinner();
      const points = this._scoreTrick();
      this.players[winner].score += points;
      this.turn = winner;
      this.trick = [];
      this._emit('updateScore', this.players.map(p => ({ id: p.id, score: p.score })));
      this._emit('trickComplete', null);
      this._emitBoard();
      this._checkRoundEnd();
      this._advanceIfBotsTurn();
      return;
    }

    this.turn = (this.turn + 1) % 4;
    this._emit('highlightPlayer', this.turn);
    this._emitBoard();
    this._advanceIfBotsTurn();
  }

  _emit(action, data) {
    if (typeof this.ui === 'function') this.ui(action, data);
  }

  _emitBoard() {
    this._emit('updateBoard', {
      players: this.players,
      trick: this.trick,
      contract: this.contract || 'complex'
    });
    this._emit('highlightPlayer', this.turn);
    if (this.turn === 0) this._emit('enableInput', null);
  }

  _resetForNewRound() {
    this.turn = 0;
    this.contract = null;
    this.trick = [];
    this.round += 1;
    this.started = false;
    this.players.forEach(p => { p.hand = []; p.score = 0; });
    const deck = this._makeDeck();
    this._shuffle(deck);
    for (let i = 0; i < 52; i++) {
      this.players[i % 4].hand.push(deck[i]);
    }
    this.players.forEach(p => p.hand.sort(this._cardSort));
    this._emit('message', 'اختر العقد للبدء.');
  }

  _makeDeck() {
    const suits = ['♠', '♥', '♦', '♣'];
    const ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];
    const deck = [];
    for (const s of suits) {
      for (const r of ranks) deck.push({ suit: s, rank: r });
    }
    return deck;
  }

  _shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const t = arr[i];
      arr[i] = arr[j];
      arr[j] = t;
    }
  }

  _rankValue(r) {
    if (r === 'A') return 14;
    if (r === 'K') return 13;
    if (r === 'Q') return 12;
    if (r === 'J') return 11;
    return parseInt(r, 10);
  }

  _suitValue(s) {
    if (s === '♣') return 1;
    if (s === '♦') return 2;
    if (s === '♥') return 3;
    return 4;
  }

  _cardSort = (a, b) => {
    const sv = this._suitValue(a.suit) - this._suitValue(b.suit);
    if (sv !== 0) return sv;
    return this._rankValue(a.rank) - this._rankValue(b.rank);
  };

  _leadSuit() {
    if (!this.trick.length) return null;
    return this.trick[0].card.suit;
  }

  _playerHasSuit(playerId, suit) {
    const h = this.players[playerId].hand;
    for (const c of h) if (c.suit === suit) return true;
    return false;
  }

  _isMoveLegal(playerId, card) {
    const lead = this._leadSuit();
    if (!lead) return true;
    if (card.suit === lead) return true;
    return !this._playerHasSuit(playerId, lead);
  }

  _resolveTrickWinner() {
    const lead = this._leadSuit();
    let winner = this.trick[0].player;
    let best = this.trick[0].card;
    for (let i = 1; i < this.trick.length; i++) {
      const cur = this.trick[i];
      if (cur.card.suit !== lead) continue;
      if (this._rankValue(cur.card.rank) > this._rankValue(best.rank)) {
        best = cur.card;
        winner = cur.player;
      }
    }
    return winner;
  }

  _scoreTrick() {
    let points = 0;
    for (const t of this.trick) {
      const c = t.card;
      if (this.contract === 'queens' && c.rank === 'Q') points += 25;
      if (this.contract === 'diamonds' && c.suit === '♦') points += 10;
      if (this.contract === 'king' && c.rank === 'K' && c.suit === '♥') points += 75;
      if (this.contract === 'slapping') {
        if (c.rank === 'J' && c.suit === '♣') points += 10;
        if (c.rank === 'Q' && c.suit === '♠') points += 10;
        if (c.rank === 'K' && c.suit === '♠') points += 10;
        if (c.rank === 'A' && c.suit === '♠') points += 10;
        if (c.rank === '10' && c.suit === '♦') points += 10;
      }
      if (this.contract === 'complex') {
        if (c.rank === 'Q') points += 10;
        if (c.suit === '♦') points += 2;
        if (c.rank === 'K' && c.suit === '♥') points += 25;
      }
    }
    return points;
  }

  _checkRoundEnd() {
    const remaining = this.players.reduce((n, p) => n + p.hand.length, 0);
    if (remaining === 0) {
      const best = this.players.reduce((a, b) => (a.score > b.score ? a : b));
      this._emit('message', `انتهت الجولة. الفائز: ${best.name}`);
      this.started = false;
      this._emit('showContractSelector', { player: this.players[0] });
    }
  }

  _botChooseCard(playerId) {
    const player = this.players[playerId];
    if (!player.hand.length) return null;
    const lead = this._leadSuit();
    if (!lead) return 0;
    for (let i = 0; i < player.hand.length; i++) {
      if (player.hand[i].suit === lead) return i;
    }
    return 0;
  }

  _advanceIfBotsTurn() {
    if (!this.started) return;
    if (this.turn === 0) return;
    const pid = this.turn;
    const idx = this._botChooseCard(pid);
    setTimeout(() => {
      this.playCard(pid, idx);
    }, 420);
  }
}

window.TrixGame = TrixGame;

