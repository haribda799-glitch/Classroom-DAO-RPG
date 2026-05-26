# pragma version ^0.4.0

"""
@title Classroom DAO V7 - RPG Edition
@author Antigravity
@notice Educational platform contract with voter rights, RPG leveling and tokens.
@dev V7: Token Sinks — Item Burning, Recycling, and XP Transformation.
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

# ── V7: Token Sink Events ──────────────────────────────────────────────────────

event ConsumableActivated:
    student: indexed(address)
    item_id: uint256

event ItemRecycled:
    student: indexed(address)
    item_id: uint256
    sgc_refund: uint256

event ItemTransformedToXP:
    student: indexed(address)
    item_id: uint256
    xp_gained: uint256

# ── Structs ────────────────────────────────────────────────────────────────────

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
    item_type: uint256      # 1=Consumable, 2=Recyclable, 3=XP Transform, 4=Status
    refund_percent: uint256 # Used for type 2: percentage of price refunded (0–100)
    xp_bonus: uint256       # Used for type 3: XP granted on transform

struct PurchaseLog:
    student: address
    item_name: String[64]
    price: uint256
    timestamp: uint256

# ── State Variables ────────────────────────────────────────────────────────────

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
current_attendance_reward: public(uint256)
has_claimed_attendance: public(HashMap[address, bytes32])

student_inventory: public(HashMap[address, DynArray[uint256, 50]])
market_purchases: public(DynArray[PurchaseLog, 1024])

marketItems: public(HashMap[uint256, MarketItem])
marketItemCount: public(uint256)

# V7: Parallel quantity tracker for token sink decrements (O(1) per item)
student_item_count: public(HashMap[address, HashMap[uint256, uint256]])

questNames: public(HashMap[uint256, String[100]])

currentPollId: public(uint256)
pollVotes: public(HashMap[uint256, HashMap[uint256, uint256]])
hasVoted: public(HashMap[uint256, HashMap[address, bool]])
receivedDelegations: public(HashMap[uint256, HashMap[address, uint256]])
roundVote: public(HashMap[uint256, HashMap[address, uint256]])

# ── Constructor ────────────────────────────────────────────────────────────────

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

# ── Student Registration ───────────────────────────────────────────────────────

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

# ── Rewards ────────────────────────────────────────────────────────────────────

@external
def rewardStudent(addr: address, amount: uint256, reason: String[100]):
    """
    @notice Reward student with XP and SGC.
    @dev May only be called by `chairperson`.
    @param amount The amount of XP. Corresponding SGC tokens will be scaled by 10**18.
    """
    assert msg.sender == self.chairperson, "Only Game Master can reward"
    assert self.voters[addr].weight > 0, "Not a registered student"

    self.students[addr].academicXP += amount

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

# ── Attendance ─────────────────────────────────────────────────────────────────

@external
def generateDailyCode(code_hash: bytes32, reward_amount: uint256):
    """
    @notice Generates a daily attendance code hash, valid for 5 minutes.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "Only Game Master can generate code"
    self.active_code_hash = code_hash
    self.code_expiration_time = block.timestamp + 300
    self.current_attendance_reward = reward_amount

@external
def claimAttendance(code: String[32]):
    """
    @notice Claim attendance using the daily code. Rewards dynamic XP and SGC.
    """
    assert self.voters[msg.sender].weight > 0, "Not a registered student"
    assert block.timestamp <= self.code_expiration_time, "Time is up!"

    code_hash: bytes32 = keccak256(code)
    assert code_hash == self.active_code_hash, "Invalid code"
    assert self.has_claimed_attendance[msg.sender] != code_hash, "Already claimed"

    self.has_claimed_attendance[msg.sender] = code_hash

    amount: uint256 = self.current_attendance_reward
    self.students[msg.sender].academicXP += amount

    sgc_amount: uint256 = amount * 10**18
    extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, msg.sender, sgc_amount)

    log AttendanceClaimed(student=msg.sender, xp_rewarded=amount)
    log StudentRewarded(student=msg.sender, amount=amount, sgc_amount=sgc_amount, reason="Attendance")

# ── Market Management ──────────────────────────────────────────────────────────

@external
def addMarketItem(
    name: String[64],
    price: uint256,
    item_type: uint256,
    refund_percent: uint256,
    xp_bonus: uint256
):
    """
    @notice Adds an item to the Smart Market with full V7 economic properties.
    @dev May only be called by `chairperson`.
    @param name Display name of the item.
    @param price Cost in SGC (without decimals; stored as-is, converted on buy).
    @param item_type 1=Consumable, 2=Recyclable, 3=XP Transform, 4=Status.
    @param refund_percent For type 2: percentage of price returned on recycle (0-100).
    @param xp_bonus For type 3: amount of academicXP granted on transform.
    """
    assert msg.sender == self.chairperson, "Only Game Master can add items"
    assert item_type >= 1 and item_type <= 4, "Invalid item type"
    assert refund_percent <= 100, "Refund percent must be 0-100"

    self.marketItems[self.marketItemCount] = MarketItem(
        name=name,
        price=price,
        isActive=True,
        item_type=item_type,
        refund_percent=refund_percent,
        xp_bonus=xp_bonus
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

# ── Market Purchases ───────────────────────────────────────────────────────────

@external
def buyItem(itemId: uint256):
    """
    @notice Buy an item from the Smart Market. Transfers SGC to the Game Master.
    @dev V7: Also increments student_item_count for sink function eligibility.
    """
    assert self.voters[msg.sender].weight > 0, "Not a registered student"
    assert itemId < self.marketItemCount, "Invalid item ID"

    item: MarketItem = self.marketItems[itemId]
    assert item.isActive, "Item is not active"

    price_wei: uint256 = item.price * 10**18
    success: bool = extcall ERC20(self.token_address).transferFrom(msg.sender, self.chairperson_wallet, price_wei)
    assert success, "Transfer failed"

    # Track in DynArray (for market logs / display)
    self.student_inventory[msg.sender].append(itemId)

    # V7: Track quantity for sink eligibility
    self.student_item_count[msg.sender][itemId] += 1

    self.market_purchases.append(PurchaseLog(
        student=msg.sender,
        item_name=item.name,
        price=item.price,
        timestamp=block.timestamp
    ))

    log ItemPurchased(student=msg.sender, item_name=item.name, price=item.price)

# ── V7: Token Sink Functions ───────────────────────────────────────────────────

@external
def activate_consumable_item(item_id: uint256):
    """
    @notice Activate (burn) a consumable item from the student's inventory.
    @dev Checks type==1, decrements count, emits ConsumableActivated.
         The bonus/effect is recorded off-chain via the event log.
    """
    assert self.voters[msg.sender].weight > 0, "Not a registered student"
    assert item_id < self.marketItemCount, "Invalid item ID"
    assert self.student_item_count[msg.sender][item_id] > 0, "You don't own this item"

    item: MarketItem = self.marketItems[item_id]
    assert item.item_type == 1, "Item is not a consumable"

    self.student_item_count[msg.sender][item_id] -= 1

    log ConsumableActivated(student=msg.sender, item_id=item_id)

@external
def recycle_item(item_id: uint256):
    """
    @notice Recycle an item back to the instructor for a partial SGC refund.
    @dev Checks type==2, decrements count, transfers refund from chairperson_wallet.
         Refund = item.price * item.refund_percent / 100 (in SGC, scaled to 18 decimals).
    """
    assert self.voters[msg.sender].weight > 0, "Not a registered student"
    assert item_id < self.marketItemCount, "Invalid item ID"
    assert self.student_item_count[msg.sender][item_id] > 0, "You don't own this item"

    item: MarketItem = self.marketItems[item_id]
    assert item.item_type == 2, "Item is not recyclable"

    self.student_item_count[msg.sender][item_id] -= 1

    # Calculate SGC refund in wei (price is stored without decimals)
    refund_sgc: uint256 = (item.price * item.refund_percent) // 100
    refund_wei: uint256 = refund_sgc * 10**18

    if refund_wei > 0:
        extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, msg.sender, refund_wei)

    log ItemRecycled(student=msg.sender, item_id=item_id, sgc_refund=refund_wei)

@external
def transform_item_to_xp(item_id: uint256):
    """
    @notice Burn a status item to permanently transform it into Academic XP.
    @dev Checks type==3, decrements count, adds xp_bonus to student's academicXP.
    """
    assert self.voters[msg.sender].weight > 0, "Not a registered student"
    assert item_id < self.marketItemCount, "Invalid item ID"
    assert self.student_item_count[msg.sender][item_id] > 0, "You don't own this item"

    item: MarketItem = self.marketItems[item_id]
    assert item.item_type == 3, "Item is not an XP transform item"

    self.student_item_count[msg.sender][item_id] -= 1

    xp_gained: uint256 = item.xp_bonus
    self.students[msg.sender].academicXP += xp_gained

    log ItemTransformedToXP(student=msg.sender, item_id=item_id, xp_gained=xp_gained)

# ── Voting / Governance ────────────────────────────────────────────────────────

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

    self.hasVoted[self.currentPollId][msg.sender] = True
    voter_weight: uint256 = self.voters[msg.sender].weight + self.receivedDelegations[self.currentPollId][msg.sender]

    if self.hasVoted[self.currentPollId][to]:
        self.pollVotes[self.currentPollId][self.roundVote[self.currentPollId][to]] += voter_weight
    else:
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

# ── View Functions ─────────────────────────────────────────────────────────────

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
    quest_name: String[100] = self.questNames[self._winning_proposal()]
    if len(quest_name) > 0:
        return self.proposals[self._winning_proposal()].name
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
