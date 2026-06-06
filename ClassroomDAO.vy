# pragma version ^0.4.0

"""
@title Classroom DAO V8 - Hybrid Guilds Edition
@author Antigravity
@notice Educational platform contract with voter rights, RPG leveling, tokens, and hybrid guilds.
@dev V8: Hybrid Guilds — 50/50 Reward Model, AI-Powered KPI Distribution, Arbitration, and Batch Migration.
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

# ── V8: Hybrid Guild Events ────────────────────────────────────────────────────

event GuildCreated:
    guild_id: indexed(uint256)
    member_count: uint256

event GuildRewardDistributed:
    guild_id: indexed(uint256)
    total_sgc: uint256
    total_xp: uint256

event GuildProposalCreated:
    proposal_id: indexed(uint256)
    guild_id: uint256
    ai_proof_hash: bytes32

event GuildProposalSigned:
    proposal_id: indexed(uint256)
    signer: indexed(address)
    approvals_count: uint256

event GuildProposalExecuted:
    proposal_id: indexed(uint256)

event GuildDisputeRaised:
    proposal_id: indexed(uint256)
    guild_id: uint256
    disputer: indexed(address)

event GuildDisputeResolved:
    proposal_id: indexed(uint256)
    guild_id: uint256
    penalty_returned: uint256

event LegacyXPImported:
    student_count: uint256

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

# ── V8: Guild Structs ──────────────────────────────────────────────────────────

struct Guild:
    guild_id: uint256
    total_xp: uint256
    member_count: uint256
    members: DynArray[address, 5]
    is_active: bool

struct GuildProposal:
    proposal_id: uint256
    guild_id: uint256
    amounts: DynArray[uint256, 5]       # Premium token distribution per member
    targets: DynArray[address, 5]       # Recipient wallet addresses
    ai_proof_hash: bytes32              # 0G Storage AI report hash
    approvals_count: uint256            # Current signature count
    is_disputed: bool                   # Arbitration freeze flag
    is_executed: bool                   # Completion flag

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

# ── V8: Hybrid Guild State ─────────────────────────────────────────────────────

guilds: public(HashMap[uint256, Guild])
guild_proposals: public(HashMap[uint256, GuildProposal])
proposal_signatures: public(HashMap[uint256, HashMap[address, bool]])
guild_vaults: public(HashMap[uint256, uint256])      # SGC balance on guild vault (base units)
guild_locked: public(HashMap[uint256, bool])         # Vault lock status (dispute freeze)
student_to_guild: public(HashMap[address, uint256])  # Student -> Guild binding (0 = unassigned)
next_proposal_id: public(uint256)

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

# ── V8: Hybrid Guild Management ───────────────────────────────────────────────

@external
def create_guild(guild_id: uint256, members: DynArray[address, 5]):
    """
    @notice Creates a new hybrid guild and binds students to it.
    @dev Only callable by chairperson (Game Master / boss_address).
         Each student can belong to exactly one guild. Guild IDs must be > 0.
         Duplicate detection is implicit: the second occurrence would see
         student_to_guild already set (non-zero) and revert.
    @param guild_id Unique guild identifier (must be > 0).
    @param members Array of registered student addresses (1-5 members).
    """
    assert msg.sender == self.chairperson, "Only Game Master can create guilds"
    assert guild_id > 0, "Guild ID must be greater than 0"
    assert len(members) > 0 and len(members) <= 5, "Guild must have 1 to 5 members"
    assert not self.guilds[guild_id].is_active, "Guild with this ID already exists"

    # Validate and bind each member in a single pass.
    # Zero addresses are treated as empty padding and silently skipped.
    real_member_count: uint256 = 0
    for m: address in members:
        if m != empty(address):
            assert self.voters[m].weight > 0, "Member is not a registered student"
            assert self.student_to_guild[m] == 0, "Student already assigned to a guild"
            self.student_to_guild[m] = guild_id
            real_member_count += 1

    assert real_member_count > 0, "Guild must have at least one real member"

    self.guilds[guild_id] = Guild(
        guild_id=guild_id,
        total_xp=0,
        member_count=real_member_count,
        members=members,
        is_active=True
    )

    log GuildCreated(guild_id=guild_id, member_count=real_member_count)


# ── V8: Hybrid Reward System (50/50 Model) ────────────────────────────────────

@external
@nonreentrant
def distribute_guild_reward(guild_id: uint256, total_sgc: uint256, total_xp: uint256):
    """
    @notice Distribute guild reward using the 50/50 hybrid model.
    @dev Only callable by chairperson.
         - Base 50% SGC: split equally among members, transferred immediately.
         - Premium 50% SGC: deposited into guild_vaults for DAO-governed distribution.
         - XP: added to guild total and split equally among members' personal XP.
    @param guild_id Target guild identifier.
    @param total_sgc Total SGC reward in base units (without 10**18 decimals).
    @param total_xp Total Academic XP reward.
    """
    assert msg.sender == self.chairperson, "Only Game Master can distribute rewards"
    assert self.guilds[guild_id].is_active, "Guild is not active"
    assert total_sgc > 0 or total_xp > 0, "Reward must be non-zero"

    guild: Guild = self.guilds[guild_id]
    member_count: uint256 = guild.member_count

    # 50/50 split: base guaranteed income + premium KPI pool
    base_share: uint256 = total_sgc // 2
    premium: uint256 = total_sgc - base_share  # Handles odd totals correctly

    # Per-member equal shares
    per_member_sgc: uint256 = base_share // member_count
    per_member_xp: uint256 = total_xp // member_count

    # Distribute base SGC and XP to each guild member
    for i: uint256 in range(5):
        if i >= member_count:
            break
        member: address = guild.members[i]

        # Credit personal Academic XP
        self.students[member].academicXP += per_member_xp

        # Transfer base SGC share from chairperson wallet
        if per_member_sgc > 0:
            sgc_wei: uint256 = per_member_sgc * 10 ** 18
            extcall ERC20(self.token_address).transferFrom(
                self.chairperson_wallet, member, sgc_wei
            )

    # Deposit premium portion into guild vault for DAO-governed distribution
    self.guild_vaults[guild_id] += premium

    # Update guild cumulative XP
    self.guilds[guild_id].total_xp += total_xp

    log GuildRewardDistributed(guild_id=guild_id, total_sgc=total_sgc, total_xp=total_xp)


# ── V8: Internal DAO & 0G Storage Integration ─────────────────────────────────

@external
def create_distribution_proposal(
    guild_id: uint256,
    targets: DynArray[address, 5],
    amounts: DynArray[uint256, 5],
    ai_proof_hash: bytes32
):
    """
    @notice Create a proposal to distribute premium SGC from the guild vault.
    @dev Any guild member can propose. Vault must not be frozen.
         ai_proof_hash is the keccak256 of the AI analysis report stored on 0G Storage.
         Sum of amounts must exactly equal the current vault balance.
    @param guild_id Guild whose vault is being distributed.
    @param targets Recipient addresses (guild members).
    @param amounts SGC amounts per recipient (base units, sum must equal vault balance).
    @param ai_proof_hash 32-byte hash of the AI recommendation report from 0G Storage.
    """
    assert guild_id > 0, "Invalid guild ID"
    assert self.student_to_guild[msg.sender] == guild_id, "Not a member of this guild"
    assert not self.guild_locked[guild_id], "Guild vault is locked (dispute in progress)"
    assert len(targets) == len(amounts), "Targets and amounts length mismatch"
    assert len(targets) > 0, "Proposal cannot be empty"

    # Verify that proposed distribution exactly matches vault balance
    total: uint256 = 0
    for a: uint256 in amounts:
        total += a
    assert total == self.guild_vaults[guild_id], "Amounts must equal vault balance"

    proposal_id: uint256 = self.next_proposal_id

    self.guild_proposals[proposal_id] = GuildProposal(
        proposal_id=proposal_id,
        guild_id=guild_id,
        amounts=amounts,
        targets=targets,
        ai_proof_hash=ai_proof_hash,
        approvals_count=0,
        is_disputed=False,
        is_executed=False
    )

    self.next_proposal_id += 1

    log GuildProposalCreated(
        proposal_id=proposal_id,
        guild_id=guild_id,
        ai_proof_hash=ai_proof_hash
    )


@external
@nonreentrant
def sign_proposal(proposal_id: uint256):
    """
    @notice Sign a guild distribution proposal.
    @dev When all guild members sign (100% consensus), the proposal auto-executes:
         tokens are transferred from chairperson_wallet to targets and vault is cleared.
    @param proposal_id ID of the proposal to sign.
    """
    proposal: GuildProposal = self.guild_proposals[proposal_id]
    assert proposal.guild_id > 0, "Proposal does not exist"
    assert not proposal.is_executed, "Proposal already executed"
    assert not proposal.is_disputed, "Proposal is under dispute"

    guild_id: uint256 = proposal.guild_id
    assert self.student_to_guild[msg.sender] == guild_id, "Not a member of this guild"
    assert not self.proposal_signatures[proposal_id][msg.sender], "Already signed this proposal"

    # Record signature
    self.proposal_signatures[proposal_id][msg.sender] = True
    self.guild_proposals[proposal_id].approvals_count += 1

    new_count: uint256 = self.guild_proposals[proposal_id].approvals_count
    member_count: uint256 = self.guilds[guild_id].member_count

    log GuildProposalSigned(
        proposal_id=proposal_id,
        signer=msg.sender,
        approvals_count=new_count
    )

    # Auto-execute on 100% consensus (all members signed)
    if new_count == member_count:
        # Effects first: mark executed and clear vault before external calls
        self.guild_proposals[proposal_id].is_executed = True
        self.guild_vaults[guild_id] = 0

        # Interactions: distribute tokens to targets
        for i: uint256 in range(5):
            if i >= len(proposal.targets):
                break
            if proposal.amounts[i] > 0:
                sgc_wei: uint256 = proposal.amounts[i] * 10 ** 18
                extcall ERC20(self.token_address).transferFrom(
                    self.chairperson_wallet, proposal.targets[i], sgc_wei
                )

        log GuildProposalExecuted(proposal_id=proposal_id)


# ── V8: Dispute & Arbitration Mechanics ────────────────────────────────────────

@external
def raise_dispute(proposal_id: uint256):
    """
    @notice Raise a dispute against a distribution proposal.
    @dev Any guild member can dispute. This freezes the guild vault and blocks
         new proposals and withdrawals until the Game Master resolves it.
    @param proposal_id ID of the proposal to dispute.
    """
    proposal: GuildProposal = self.guild_proposals[proposal_id]
    assert proposal.guild_id > 0, "Proposal does not exist"
    assert not proposal.is_executed, "Proposal already executed"
    assert not proposal.is_disputed, "Proposal already disputed"

    guild_id: uint256 = proposal.guild_id
    assert self.student_to_guild[msg.sender] == guild_id, "Not a member of this guild"

    # Freeze proposal and lock guild vault
    self.guild_proposals[proposal_id].is_disputed = True
    self.guild_locked[guild_id] = True

    log GuildDisputeRaised(
        proposal_id=proposal_id,
        guild_id=guild_id,
        disputer=msg.sender
    )


@external
@nonreentrant
def resolve_dispute(
    proposal_id: uint256,
    final_targets: DynArray[address, 5],
    final_amounts: DynArray[uint256, 5]
):
    """
    @notice Resolve a disputed proposal via Game Master arbitration.
    @dev 10% penalty is confiscated (remains on chairperson_wallet for future bounties).
         Remaining 90% is distributed according to the Game Master's final decision.
    @param proposal_id ID of the disputed proposal.
    @param final_targets Addresses to receive the remaining 90%.
    @param final_amounts SGC amounts per target (must sum to 90% of vault after penalty).
    """
    assert msg.sender == self.chairperson, "Only Game Master can resolve disputes"

    proposal: GuildProposal = self.guild_proposals[proposal_id]
    assert proposal.is_disputed, "Proposal is not under dispute"
    assert not proposal.is_executed, "Proposal already executed"
    assert len(final_targets) == len(final_amounts), "Targets and amounts length mismatch"

    guild_id: uint256 = proposal.guild_id
    vault_balance: uint256 = self.guild_vaults[guild_id]

    # Calculate 10% penalty (confiscated — stays on chairperson_wallet for future bounties)
    penalty: uint256 = vault_balance // 10
    remaining: uint256 = vault_balance - penalty

    # Verify final distribution matches the remaining 90%
    total: uint256 = 0
    for a: uint256 in final_amounts:
        total += a
    assert total == remaining, "Final amounts must equal 90 pct of vault after penalty"

    # Effects: finalize state before external calls
    self.guild_proposals[proposal_id].is_executed = True
    self.guild_vaults[guild_id] = 0
    self.guild_locked[guild_id] = False

    # Interactions: distribute remaining tokens per arbitration decision
    for i: uint256 in range(5):
        if i >= len(final_targets):
            break
        if final_amounts[i] > 0:
            sgc_wei: uint256 = final_amounts[i] * 10 ** 18
            extcall ERC20(self.token_address).transferFrom(
                self.chairperson_wallet, final_targets[i], sgc_wei
            )

    log GuildDisputeResolved(
        proposal_id=proposal_id,
        guild_id=guild_id,
        penalty_returned=penalty
    )


# ── V8: Batch Data Migration ──────────────────────────────────────────────────

@external
def batch_import_legacy_xp(
    students_list: DynArray[address, 20],
    legacy_xp: DynArray[uint256, 20]
):
    """
    @notice Batch-import historical Academic XP after contract redeployment.
    @dev Only callable by chairperson. Additive — does not reset existing XP.
         Used to restore player levels from a previous contract version.
    @param students_list Array of student wallet addresses (up to 20).
    @param legacy_xp Array of XP values to credit (must match students_list length).
    """
    assert msg.sender == self.chairperson, "Only Game Master can import legacy data"
    assert len(students_list) == len(legacy_xp), "Arrays length mismatch"

    for i: uint256 in range(20):
        if i >= len(students_list):
            break
        self.students[students_list[i]].academicXP += legacy_xp[i]

    log LegacyXPImported(student_count=len(students_list))


# ── V8: Guild View Functions ───────────────────────────────────────────────────

@external
@view
def get_guild_members(guild_id: uint256) -> DynArray[address, 5]:
    """
    @notice Returns the list of member addresses for a given guild.
    @param guild_id The guild to query.
    """
    return self.guilds[guild_id].members

@external
@view
def get_guild_vault_balance(guild_id: uint256) -> uint256:
    """
    @notice Returns the current SGC balance in the guild vault (base units).
    @param guild_id The guild to query.
    """
    return self.guild_vaults[guild_id]


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
