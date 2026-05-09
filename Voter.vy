# pragma version ^0.4.0

"""
@title Voting Contract
@author Antigravity
@notice A complex voting contract with delegation and winner counting.
"""

interface ERC20:
    def transferFrom(_from: address, _to: address, _value: uint256) -> bool: nonpayable

event Voted:
    voter: indexed(address)
    proposal: uint256
    weight: uint256

event Delegated:
    voter: indexed(address)
    delegate: indexed(address)

struct Voter:
    weight: uint256
    voted: bool
    delegate: address
    vote: uint256

struct Proposal:
    name: String[32]
    voteCount: uint256

chairperson: public(address)
voters: public(HashMap[address, Voter])
proposals: public(DynArray[Proposal, 128])

token_address: public(address)
reward_amount: public(uint256)
chairperson_wallet: public(address)
has_received_reward: public(HashMap[address, bool])

@deploy
def __init__(proposalNames: DynArray[String[32], 128], _token_address: address):
    """
    @notice Create a new ballot to choose one of `proposalNames`.
    @param proposalNames Names of the proposals.
    @param _token_address Address of the SGC Token.
    """
    self.chairperson = msg.sender
    self.chairperson_wallet = msg.sender
    self.token_address = _token_address
    self.reward_amount = 100 * 10**18
    self.voters[self.chairperson].weight = 1

    for name: String[32] in proposalNames:
        self.proposals.append(Proposal(name=name, voteCount=0))

@external
@payable
def give_right_to_vote(voter: address):
    """
    @notice Give `voter` the right to vote on this ballot.
    @dev May only be called by `chairperson`.
    @param voter Address of the voter.
    """
    assert msg.sender == self.chairperson, "Only chairperson can give right to vote"
    assert not self.voters[voter].voted, "The voter already voted"
    assert self.voters[voter].weight == 0, "The voter already has rights"
    assert msg.value == 10000000000000000, "Exact 0.01 OGI required"

    self.voters[voter].weight = 1
    send(voter, msg.value)

@external
def delegate(to: address):
    """
    @notice Delegate your vote to the voter `to`.
    @param to Address to which vote is delegated.
    """
    assert not self.voters[msg.sender].voted, "You already voted"
    assert to != msg.sender, "Self-delegation is disallowed"

    # Forward delegation if `to` also delegated.
    # In Vyper, we have to be careful with loops.
    # We limit the depth to avoid infinite loops and gas issues.
    curr: address = to
    for i: uint256 in range(10):
        if self.voters[curr].delegate == empty(address):
            break
        curr = self.voters[curr].delegate
        assert curr != msg.sender, "Found loop in delegation"

    voter: Voter = self.voters[msg.sender]
    voter.voted = True
    voter.delegate = curr
    self.voters[msg.sender] = voter

    log Delegated(voter=msg.sender, delegate=curr)

    delegate_: Voter = self.voters[curr]
    if delegate_.voted:
        # If the delegate already voted, directly add to the number of votes
        self.proposals[delegate_.vote].voteCount += voter.weight
    else:
        # If the delegate has not voted yet, add to her weight.
        delegate_.weight += voter.weight
        self.voters[curr] = delegate_

@external
def vote(proposalIndex: uint256):
    """
    @notice Give your vote (including votes delegated to you)
    to proposal `proposals[proposalIndex].name`.
    @param proposalIndex Index of proposal in the proposals array.
    """
    voter: Voter = self.voters[msg.sender]
    assert voter.weight != 0, "Has no right to vote"
    assert not voter.voted, "Already voted"
    assert proposalIndex < len(self.proposals), "Invalid proposal index"
    assert not self.has_received_reward[msg.sender], "Already received reward"

    voter.voted = True
    voter.vote = proposalIndex
    self.voters[msg.sender] = voter

    self.proposals[proposalIndex].voteCount += voter.weight

    log Voted(voter=msg.sender, proposal=proposalIndex, weight=voter.weight)
    
    # Reward
    self.has_received_reward[msg.sender] = True
    extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, msg.sender, self.reward_amount)

@internal
@view
def _winning_proposal() -> uint256:
    """
    @notice Computes the winning proposal taking all previous votes into account.
    @return winningProposal_ index of winning proposal in the proposals array.
    """
    winning_vote_count: uint256 = 0
    winning_proposal_index: uint256 = 0
    num_proposals: uint256 = len(self.proposals)
    
    for i: uint256 in range(128):
        if i >= num_proposals:
            break
            
        c: uint256 = self.proposals[i].voteCount
        if c > winning_vote_count:
            winning_vote_count = c
            winning_proposal_index = i
    return winning_proposal_index

@external
@view
def winning_proposal() -> uint256:
    """
    @notice Computes the winning proposal taking all previous votes into account.
    @return winningProposal_ index of winning proposal in the proposals array.
    """
    return self._winning_proposal()

@external
@view
def winner_name() -> String[32]:
    """
    @notice Calls winning_proposal() function to get the index
    of the winner contained in the proposals array and then
    returns the name of the winner.
    @return winnerName_ the name of the winner.
    """
    return self.proposals[self._winning_proposal()].name

