# pragma version ^0.4.0

"""
@title Classroom DAO V4 - RPG Edition
@author Antigravity
@notice Educational platform contract with voter rights, RPG leveling and tokens.
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

event StudentRegistered:
    student: indexed(address)
    nickname: String[64]
    group: String[32]

event StudentRewarded:
    student: indexed(address)
    amount: uint256
    sgc_amount: uint256
    reason: String[100]

event AttendanceClaimed:
    student: indexed(address)
    xp_rewarded: uint256

event ItemPurchased:
    student: indexed(address)
    item_name: String[64]
    price: uint256

event NewRoundStarted:
    pollId: uint256

struct Voter:
    weight: uint256
    voted: bool
    delegate: address
    vote: uint256

struct Proposal:
    name: String[32]
    voteCount: uint256

struct Student:
    nickname: String[64]
    group: String[32]
    academicXP: uint256
    is_hidden: bool

struct MarketItem:
    name: String[64]
    price: uint256
    isActive: bool

struct PurchaseLog:
    student: address
    item_name: String[64]
    price: uint256
    timestamp: uint256

chairperson: public(address)
voters: public(HashMap[address, Voter])
proposals: public(DynArray[Proposal, 128])

students: public(HashMap[address, Student])
student_addresses: public(DynArray[address, 1024])
used_nicknames: public(HashMap[String[64], bool])

token_address: public(address)
reward_amount: public(uint256)
chairperson_wallet: public(address)
has_received_reward: public(HashMap[address, bool])

active_code_hash: public(bytes32)
code_expiration_time: public(uint256)
has_claimed_attendance: public(HashMap[address, bytes32])

student_inventory: public(HashMap[address, DynArray[uint256, 50]])
market_purchases: public(DynArray[PurchaseLog, 1024])

marketItems: public(HashMap[uint256, MarketItem])
marketItemCount: public(uint256)

questNames: public(HashMap[uint256, String[100]])

currentPollId: public(uint256)
pollVotes: public(HashMap[uint256, HashMap[uint256, uint256]])
hasVoted: public(HashMap[uint256, HashMap[address, bool]])
receivedDelegations: public(HashMap[uint256, HashMap[address, uint256]])
roundVote: public(HashMap[uint256, HashMap[address, uint256]])

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
    self.currentPollId = 1

    for name: String[32] in proposalNames:
        self.proposals.append(Proposal(name=name, voteCount=0))

@external
@payable
def registerStudent(addr: address, nickname: String[64], group: String[32]):
    """
    @notice Register a student, give them voting rights and exact 0.01 OGI for gas.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "Only Game Master can register"
    assert not self.voters[addr].voted, "The voter already voted"
    assert self.voters[addr].weight == 0, "The student already has rights"
    assert not self.used_nicknames[nickname], "Nickname already taken"
    assert msg.value == 10000000000000000, "Exact 0.01 OGI required"
    assert len(self.student_addresses) < 1024, "Max students reached"

    self.voters[addr].weight = 1
    self.used_nicknames[nickname] = True
    
    # Init student
    self.students[addr] = Student(
        nickname=nickname,
        group=group,
        academicXP=0,
        is_hidden=False
    )
    self.student_addresses.append(addr)
    
    send(addr, msg.value)
    
    log StudentRegistered(student=addr, nickname=nickname, group=group)

@external
def setPrivacy(hidden: bool):
    """
    @notice Allows a student to hide their wallet address from the public leaderboard.
    """
    assert self.voters[msg.sender].weight > 0, "Not a registered student"
    self.students[msg.sender].is_hidden = hidden

@external
def rewardStudent(addr: address, amount: uint256, reason: String[100]):
    """
    @notice Reward student with XP and SGC.
    @dev May only be called by `chairperson`.
    @param amount The amount of XP. Corresponding SGC tokens will be scaled by 10**18.
    """
    assert msg.sender == self.chairperson, "Only Game Master can reward"
    assert self.voters[addr].weight > 0, "Not a registered student"
    
    # Increase XP
    self.students[addr].academicXP += amount
    
    # Transfer SGC (1:1 with XP but taking 18 decimals into account)
    sgc_amount: uint256 = amount * 10**18
    
    extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, addr, sgc_amount)
    
    log StudentRewarded(student=addr, amount=amount, sgc_amount=sgc_amount, reason=reason)

@external
def rewardBatch(addrs: DynArray[address, 256], amount: uint256, reason: String[100]):
    """
    @notice Reward multiple students with XP and SGC.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "Only Game Master can reward"
    
    sgc_amount: uint256 = amount * 10**18
    
    for addr: address in addrs:
        assert self.voters[addr].weight > 0, "Not a registered student"
        self.students[addr].academicXP += amount
        extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, addr, sgc_amount)
        log StudentRewarded(student=addr, amount=amount, sgc_amount=sgc_amount, reason=reason)

@external
def generateDailyCode(code_hash: bytes32):
    """
    @notice Generates a daily attendance code hash, valid for 5 minutes.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "Only Game Master can generate code"
    self.active_code_hash = code_hash
    self.code_expiration_time = block.timestamp + 300

@external
def claimAttendance(code: String[32]):
    """
    @notice Claim attendance using the daily code. Rewards 50 XP and 50 SGC.
    """
    assert self.voters[msg.sender].weight > 0, "Not a registered student"
    assert block.timestamp <= self.code_expiration_time, "Time is up!"
    
    code_hash: bytes32 = keccak256(code)
    assert code_hash == self.active_code_hash, "Invalid code"
    assert self.has_claimed_attendance[msg.sender] != code_hash, "Already claimed"
    
    self.has_claimed_attendance[msg.sender] = code_hash
    
    amount: uint256 = 50
    self.students[msg.sender].academicXP += amount
    
    sgc_amount: uint256 = amount * 10**18
    extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, msg.sender, sgc_amount)
    
    log AttendanceClaimed(student=msg.sender, xp_rewarded=amount)
    log StudentRewarded(student=msg.sender, amount=amount, sgc_amount=sgc_amount, reason="Attendance")

@external
def addMarketItem(name: String[64], price: uint256):
    """
    @notice Adds an item to the Smart Market.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "Only Game Master can add items"
    self.marketItems[self.marketItemCount] = MarketItem(
        name=name,
        price=price,
        isActive=True
    )
    self.marketItemCount += 1

@external
def setMarketItemActive(itemId: uint256, active: bool):
    """
    @notice Sets the active status of an item.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "Only Game Master can update items"
    assert itemId < self.marketItemCount, "Invalid item ID"
    self.marketItems[itemId].isActive = active

@external
def buyItem(itemId: uint256):
    """
    @notice Buy an item from the Smart Market. Transfers SGC to the Game Master.
    """
    assert self.voters[msg.sender].weight > 0, "Not a registered student"
    assert itemId < self.marketItemCount, "Invalid item ID"
    
    item: MarketItem = self.marketItems[itemId]
    assert item.isActive, "Item is not active"
    
    price_wei: uint256 = item.price * 10**18
    success: bool = extcall ERC20(self.token_address).transferFrom(msg.sender, self.chairperson_wallet, price_wei)
    assert success, "Transfer failed"
    
    self.student_inventory[msg.sender].append(itemId)
    self.market_purchases.append(PurchaseLog({
        student: msg.sender,
        item_name: item.name,
        price: item.price,
        timestamp: block.timestamp
    }))
    
    log ItemPurchased(student=msg.sender, item_name=item.name, price=item.price)

@external
def setQuestNames(names: DynArray[String[100], 4]):
    """
    @notice Sets the names of the Voting Quests.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "Only Game Master can set quest names"
    for i: uint256 in range(4):
        if i < len(names):
            self.questNames[i] = names[i]
        else:
            self.questNames[i] = ""

@external
def startNewRound():
    """
    @notice Starts a new voting round.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "Only Game Master can start a round"
    self.currentPollId += 1
    log NewRoundStarted(pollId=self.currentPollId)

@external
def delegate(to: address):
    """
    @notice Delegate your vote to the voter `to`.
    @param to Address to which vote is delegated.
    """
    assert self.voters[msg.sender].weight > 0, "Not a registered student"
    assert not self.hasVoted[self.currentPollId][msg.sender], "You already voted this round"
    assert to != msg.sender, "Self-delegation is disallowed"
    assert self.voters[to].weight > 0, "Delegate is not a registered student"

    # For multi-round, we do a single-level delegation to avoid complex loops.
    # The weight transferred includes the sender's base weight + any delegations they received this round.
    self.hasVoted[self.currentPollId][msg.sender] = True
    voter_weight: uint256 = self.voters[msg.sender].weight + self.receivedDelegations[self.currentPollId][msg.sender]

    if self.hasVoted[self.currentPollId][to]:
        # Delegate already voted, add directly to their chosen proposal
        self.pollVotes[self.currentPollId][self.roundVote[self.currentPollId][to]] += voter_weight
    else:
        # Delegate hasn't voted yet, add to their weight for this round
        self.receivedDelegations[self.currentPollId][to] += voter_weight

    log Delegated(voter=msg.sender, delegate=to)

@external
def vote(proposalIndex: uint256):
    """
    @notice Give your vote to proposal `proposals[proposalIndex].name`.
    @param proposalIndex Index of proposal in the proposals array.
    """
    assert self.voters[msg.sender].weight > 0, "Has no right to vote"
    assert not self.hasVoted[self.currentPollId][msg.sender], "Already voted this round"
    assert proposalIndex < len(self.proposals), "Invalid proposal index"

    self.hasVoted[self.currentPollId][msg.sender] = True
    self.roundVote[self.currentPollId][msg.sender] = proposalIndex

    voter_weight: uint256 = self.voters[msg.sender].weight + self.receivedDelegations[self.currentPollId][msg.sender]
    self.pollVotes[self.currentPollId][proposalIndex] += voter_weight

    log Voted(voter=msg.sender, proposal=proposalIndex, weight=voter_weight)
    
    # Reward for the first vote ever
    if not self.has_received_reward[msg.sender]:
        self.has_received_reward[msg.sender] = True
        extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, msg.sender, self.reward_amount)

@internal
@view
def _winning_proposal() -> uint256:
    winning_vote_count: uint256 = 0
    winning_proposal_index: uint256 = 0
    num_proposals: uint256 = len(self.proposals)
    
    for i: uint256 in range(128):
        if i >= num_proposals:
            break
            
        c: uint256 = self.pollVotes[self.currentPollId][i]
        if c > winning_vote_count:
            winning_vote_count = c
            winning_proposal_index = i
    return winning_proposal_index

@external
@view
def winning_proposal() -> uint256:
    return self._winning_proposal()

@external
@view
def winner_name() -> String[32]:
    # Try fetching from questNames first, fallback to proposals array
    quest_name: String[100] = self.questNames[self._winning_proposal()]
    if len(quest_name) > 0:
        # Vyper string casting for return
        return self.proposals[self._winning_proposal()].name # Or just return proposals name. We use frontend to display questNames anyway.
    return self.proposals[self._winning_proposal()].name

@external
@view
def get_student_count() -> uint256:
    return len(self.student_addresses)

@external
@view
def get_student_inventory(student: address) -> DynArray[uint256, 50]:
    return self.student_inventory[student]

@external
@view
def get_market_purchases() -> DynArray[PurchaseLog, 1024]:
    return self.market_purchases
