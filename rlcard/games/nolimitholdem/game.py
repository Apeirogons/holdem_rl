from enum import Enum

import numpy as np
from copy import deepcopy
from rlcard.games.limitholdem import Game
from rlcard.games.limitholdem import PlayerStatus

from rlcard.games.nolimitholdem import Dealer
from rlcard.games.nolimitholdem import Player
from rlcard.games.nolimitholdem import Judger
from rlcard.games.nolimitholdem import Round, Action


class Stage(Enum):

    PREFLOP = 0
    FLOP = 1
    TURN = 2
    RIVER = 3
    END_HIDDEN = 4
    SHOWDOWN = 5


class NolimitholdemGame(Game):

    def __init__(self, allow_step_back=False, num_players=2):
        ''' Initialize the class nolimitholdem Game
        '''
        self.allow_step_back = allow_step_back
        self.np_random = np.random.RandomState()

        # small blind and big blind
        self.small_blind = 1
        self.big_blind = 2 * self.small_blind

        # config players
        self.num_players = num_players
        self.init_chips = 100

    def init_game(self):
        ''' Initialilze the game of Limit Texas Hold'em

        This version supports two-player limit texas hold'em

        Returns:
            (tuple): Tuple containing:

                (dict): The first state of the game
                (int): Current player's id
        '''
        # Initilize a dealer that can deal cards
        self.dealer = Dealer(self.np_random)

        # Initilize two players to play the game
        self.players = [Player(i, self.init_chips, self.np_random) for i in range(self.num_players)]

        # Initialize a judger class which will decide who wins in the end
        self.judger = Judger(self.np_random)

        # Deal cards to each  player to prepare for the first round
        for i in range(2 * self.num_players):
            self.players[i % self.num_players].hand.append(self.dealer.deal_card())

        # Initilize public cards
        self.public_cards = []
        self.stage = Stage.PREFLOP

        # Randomly choose a big blind and a small blind
        s = self.np_random.randint(0, self.num_players)
        b = (s + 1) % self.num_players
        self.players[b].bet(chips=self.big_blind)
        self.players[s].bet(chips=self.small_blind)

        # The player next to the small blind plays the first
        self.game_pointer = (b + 1) % self.num_players

        # Initilize a bidding round, in the first round, the big blind and the small blind needs to
        # be passed to the round for processing.
        self.round = Round(self.num_players, self.big_blind, dealer=self.dealer, np_random=self.np_random)

        self.round.start_new_round(game_pointer=self.game_pointer, raised=[p.in_chips for p in self.players])

        # Count the round. There are 4 rounds in each game.
        self.round_counter = 0

        # Save the hisory for stepping back to the last state.
        self.history = []
        self.action_history = []

        state = self.get_state(self.game_pointer)

        return state, self.game_pointer

    def get_legal_actions(self):
        ''' Return the legal actions for current player

        Returns:
            (list): A list of legal actions
        '''
        return self.round.get_nolimit_legal_actions(players=self.players)

    def step(self, action):
        ''' Get the next state

        Args:
            action (str): a specific action. (call, raise, fold, or check)

        Returns:
            (tuple): Tuple containing:

                (dict): next player's state
                (int): next plater's id
        '''

        if action not in self.get_legal_actions():
            print(action, self.get_legal_actions())
            print(self.get_state(self.game_pointer))
            raise Exception('Action not allowed')

        if self.allow_step_back:
            # First snapshot the current state
            r = deepcopy(self.round)
            b = self.game_pointer
            r_c = self.round_counter
            d = deepcopy(self.dealer)
            p = deepcopy(self.public_cards)
            ps = deepcopy(self.players)
            ac = deepcopy(self.action_history)
            self.history.append((r, b, r_c, d, p, ps, ac))

        # Then we proceed to the next round
        self.action_history.append([self.game_pointer, self.round_counter, action])
        self.game_pointer = self.round.proceed_round(self.players, action)

        players_in_bypass = [1 if player.status in (PlayerStatus.FOLDED, PlayerStatus.ALLIN) else 0 for player in self.players]

        # If a round is over, we deal more public cards
        if self.round.is_over():
            # For the first round, we deal 3 cards
            if self.round_counter == 0:
                self.stage = Stage.FLOP
                self.public_cards.append(self.dealer.deal_card())
                self.public_cards.append(self.dealer.deal_card())
                self.public_cards.append(self.dealer.deal_card())
                if len(self.players) == np.sum(players_in_bypass):
                    self.round_counter += 1
                    self.stage = Stage.TURN
                    self.public_cards.append(self.dealer.deal_card())
                    self.round_counter += 1
                    self.stage = Stage.RIVER
                    self.public_cards.append(self.dealer.deal_card())
                    self.round_counter += 1
            # For the following rounds, we deal only 1 card
            elif self.round_counter == 1:
                self.stage = Stage.TURN
                self.public_cards.append(self.dealer.deal_card())
                if len(self.players) == np.sum(players_in_bypass):
                    self.round_counter += 1
                    self.stage = Stage.RIVER
                    self.public_cards.append(self.dealer.deal_card())
                    self.round_counter += 1
            elif self.round_counter == 2:
                self.stage = Stage.RIVER
                self.public_cards.append(self.dealer.deal_card())
                if len(self.players) == np.sum(players_in_bypass):
                    self.round_counter += 1

            self.round_counter += 1
            self.round.start_new_round(self.game_pointer)

        state = self.get_state(self.game_pointer)

        return state, self.game_pointer

    def get_state(self, player_id):
        ''' Return player's state

        Args:
            player_id (int): player id

        Returns:
            (dict): The state of the player
        '''
        self.dealer.pot = np.sum([player.in_chips for player in self.players])

        chips = [self.players[i].in_chips for i in range(self.num_players)]
        legal_actions = self.get_legal_actions()
        state = self.players[player_id].get_state(self.public_cards, chips, legal_actions)

        state['to_call'] = min(max(chips) - self.players[player_id].in_chips, self.players[player_id].remained_chips)/self.dealer.pot # New - %pot to call 
        state['to_allin'] = self.players[player_id].remained_chips/self.dealer.pot # New - %pot to all-in. Not strictly true, since you might have the most chips. But fixable.

        players_still_in = []
        state['n_others'] = -1 # New - number of others that haven't folded.
        for i, p in enumerate(self.players):
            if p.status in (PlayerStatus.ALIVE, PlayerStatus.ALLIN):
                state['n_others'] += 1
                players_still_in.append(i)
        this_player_i = self.players.index(self.players[player_id])
        
        state['already_called'] = 0
        for p in self.players:
            if p.in_chips == max(chips):
                state['already_called'] += 1

        people_before = 0
        state['action_history'] = self.action_history
    
        for action in state['action_history']:
            if action[0] in players_still_in:
                people_before += 1
            if action[0] == player_id:
                break
        state['position'] = people_before/len(players_still_in)

        state['past_aggression'] = 0
        state['street_aggression'] = 0
        for action in state['action_history']:

            if action[0] in players_still_in and action[0] != player_id:
                if action[2] == Action.RAISE_HALF_POT:
                    aggro = 0.5
                elif action[2] == Action.RAISE_POT:
                    aggro = 1
                elif action[2] == Action.ALL_IN:
                    aggro = 2.5
                else:
                    aggro = 0
                if action[1] != self.round_counter:
                    state['past_aggression'] += aggro
                else:
                    state['street_aggression'] += aggro
        
        state['need_to_call'] = (state['n_others'] + 1) - state['already_called']

        state['stakes'] = [self.players[i].remained_chips/self.dealer.pot for i in range(self.num_players)] # Edited: normalized to pot
        state['current_player'] = self.game_pointer
        state['pot'] = self.dealer.pot
        state['stage'] = self.stage
        return state

    def step_back(self):
        ''' Return to the previous state of the game

        Returns:
            (bool): True if the game steps back successfully
        '''
        if len(self.history) > 0:
            self.round, self.game_pointer, self.round_counter, self.dealer, self.public_cards, self.players, self.action_history = self.history.pop()
            return True
        return False

    def get_payoffs(self):
        ''' Return the payoffs of the game

        Returns:
            (list): Each entry corresponds to the payoff of one player
        '''
        hands = [p.hand + self.public_cards if p.status in (PlayerStatus.ALIVE, PlayerStatus.ALLIN) else None for p in self.players]
        chips_payoffs = self.judger.judge_game(self.players, hands)
        self.action_history = []
        return chips_payoffs

    @staticmethod
    def get_action_num():
        ''' Return the number of applicable actions

        Returns:
            (int): The number of actions. There are 6 actions (call, raise_half_pot, raise_pot, all_in, check and fold)
        '''
        return len(Action)


#if __name__ == "__main__":
#    game = NolimitholdemGame()
#
#    while True:
#        print('New Game')
#        state, game_pointer = game.init_game()
#        print(game_pointer, state)
#        i = 1
#        while not game.is_over():
#            i += 1
#            legal_actions = game.get_legal_actions()
#            # if i == 3:
#            #     print('Step back')
#            #     print(game.step_back())
#            #     game_pointer = game.get_player_id()
#            #     print(game_pointer)
#            #     legal_actions = game.get_legal_actions()
#
#            action = np.random.choice(legal_actions)
#            # action = input()
#            # if action != 'call' and action != 'fold' and action != 'check':
#            #     action = int(action)
#            print(game_pointer, action, legal_actions)
#            state, game_pointer = game.step(action)
#            print(game_pointer, state)
#
#        print(game.get_payoffs())
