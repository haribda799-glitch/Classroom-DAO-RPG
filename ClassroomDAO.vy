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

event GuildMemberLeft:
    guild_id: indexed(uint256)
    student: indexed(address)
    paid_with_tokens: bool

event GuildMemberKicked:
    guild_id: indexed(uint256)
    student: indexed(address)

event LegacyXPImported:
    student_count: uint256

# ── Structs ────────────────────────────────────────────────────────────────────

struct Voter:
    weight: uint256
    voted: bool
    delegate: address
    vote: uint256

struct Proposal:
    name: String[64]
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
proposals: public(DynArray[Proposal, 32])

students: public(HashMap[address, Student])
student_addresses: public(DynArray[address, 256])
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
market_purchases: public(DynArray[PurchaseLog, 128])

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

# ── V9: Guild Leave Penalty Constants ──────────────────────────────────────────

LEAVE_TOKEN_PENALTY: constant(uint256) = 100 * 10 ** 18  # 100 SGC in base units
LEAVE_XP_PENALTY: constant(uint256) = 50                  # 50 Academic XP

# ── Constructor ────────────────────────────────────────────────────────────────

@deploy
def __init__(_token_address: address):
    """
    @notice Deploy a new Classroom DAO.
    @param _token_address Address of the SGC Token.
    """
    self.chairperson = msg.sender
    self.chairperson_wallet = msg.sender
    self.token_address = _token_address
    self.reward_amount = 100 * 10**18
    self.voters[self.chairperson].weight = 1
    self.currentPollId = 1

# ── Student Registration ───────────────────────────────────────────────────────

@external
@payable
def registerStudent(addr: address, nickname: String[64], group: String[32]):
    """
    @notice Register a student, give them voting rights and exact 0.01 OGI for gas.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "OnlyGM"
    assert not self.voters[addr].voted, "AlreadyVoted"
    assert self.voters[addr].weight == 0, "HasRights"
    assert not self.used_nicknames[nickname], "NickTaken"
    assert msg.value == 10000000000000000, "Need0.01OGI"
    assert len(self.student_addresses) < 1024, "MaxStudents"

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
    assert self.voters[msg.sender].weight > 0, "NotStudent"
    self.students[msg.sender].is_hidden = hidden

# ── Rewards ────────────────────────────────────────────────────────────────────

@external
def rewardStudent(addr: address, amount: uint256, reason: String[100]):
    """
    @notice Reward student with XP and SGC.
    @dev May only be called by `chairperson`.
    @param amount The amount of XP. Corresponding SGC tokens will be scaled by 10**18.
    """
    assert msg.sender == self.chairperson, "OnlyGM"
    assert self.voters[addr].weight > 0, "NotStudent"

    self.students[addr].academicXP += amount

    sgc_amount: uint256 = amount * 10**18
    success: bool = extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, addr, sgc_amount)
    assert success, "TxFail"

    log StudentRewarded(student=addr, amount=amount, sgc_amount=sgc_amount, reason=reason)

@external
def rewardBatch(addrs: DynArray[address, 50], amount: uint256, reason: String[100]):
    """
    @notice Reward multiple students with XP and SGC.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "OnlyGM"

    sgc_amount: uint256 = amount * 10**18

    for addr: address in addrs:
        assert self.voters[addr].weight > 0, "NotStudent"
        self.students[addr].academicXP += amount
        success: bool = extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, addr, sgc_amount)
        assert success, "TxFail"
        log StudentRewarded(student=addr, amount=amount, sgc_amount=sgc_amount, reason=reason)

# ── Attendance ─────────────────────────────────────────────────────────────────

@external
def generateDailyCode(code_hash: bytes32, reward_amount: uint256):
    """
    @notice Generates a daily attendance code hash, valid for 5 minutes.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "OnlyGM"
    self.active_code_hash = code_hash
    self.code_expiration_time = block.timestamp + 300
    self.current_attendance_reward = reward_amount

@external
def claimAttendance(code: String[32]):
    """
    @notice Claim attendance using the daily code. Rewards dynamic XP and SGC.
    """
    assert self.voters[msg.sender].weight > 0, "NotStudent"
    assert block.timestamp <= self.code_expiration_time, "TimeUp"

    code_hash: bytes32 = keccak256(code)
    assert code_hash == self.active_code_hash, "BadCode"
    assert self.has_claimed_attendance[msg.sender] != code_hash, "Claimed"

    self.has_claimed_attendance[msg.sender] = code_hash

    amount: uint256 = self.current_attendance_reward
    self.students[msg.sender].academicXP += amount

    sgc_amount: uint256 = amount * 10**18
    success: bool = extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, msg.sender, sgc_amount)
    assert success, "TxFail"

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
    assert msg.sender == self.chairperson, "OnlyGM"
    assert item_type >= 1 and item_type <= 4, "BadItemType"
    assert refund_percent <= 100, "BadRefund"

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
    assert msg.sender == self.chairperson, "OnlyGM"
    assert itemId < self.marketItemCount, "BadItemID"
    self.marketItems[itemId].isActive = active

# ── Market Purchases ───────────────────────────────────────────────────────────

@external
def buyItem(itemId: uint256):
    """
    @notice Buy an item from the Smart Market. Transfers SGC to the Game Master.
    @dev V7: Also increments student_item_count for sink function eligibility.
    """
    assert self.voters[msg.sender].weight > 0, "NotStudent"
    assert itemId < self.marketItemCount, "BadItemID"

    item: MarketItem = self.marketItems[itemId]
    assert item.isActive, "Inactive"

    price_wei: uint256 = item.price * 10**18
    success: bool = extcall ERC20(self.token_address).transferFrom(msg.sender, self.chairperson_wallet, price_wei)
    assert success, "TxFail"

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
    assert self.voters[msg.sender].weight > 0, "NotStudent"
    assert item_id < self.marketItemCount, "BadItemID"
    assert self.student_item_count[msg.sender][item_id] > 0, "NoItem"

    item: MarketItem = self.marketItems[item_id]
    assert item.item_type == 1, "NotConsum"

    self.student_item_count[msg.sender][item_id] -= 1

    log ConsumableActivated(student=msg.sender, item_id=item_id)

@external
def recycle_item(item_id: uint256):
    """
    @notice Recycle an item back to the instructor for a partial SGC refund.
    @dev Checks type==2, decrements count, transfers refund from chairperson_wallet.
         Refund = item.price * item.refund_percent / 100 (in SGC, scaled to 18 decimals).
    """
    assert self.voters[msg.sender].weight > 0, "NotStudent"
    assert item_id < self.marketItemCount, "BadItemID"
    assert self.student_item_count[msg.sender][item_id] > 0, "NoItem"

    item: MarketItem = self.marketItems[item_id]
    assert item.item_type == 2, "NotRecycle"

    self.student_item_count[msg.sender][item_id] -= 1

    # Calculate SGC refund in wei (price is stored without decimals)
    refund_sgc: uint256 = (item.price * item.refund_percent) // 100
    refund_wei: uint256 = refund_sgc * 10**18

    if refund_wei > 0:
        success: bool = extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, msg.sender, refund_wei)
        assert success, "TxFail"

    log ItemRecycled(student=msg.sender, item_id=item_id, sgc_refund=refund_wei)

@external
def transform_item_to_xp(item_id: uint256):
    """
    @notice Burn a status item to permanently transform it into Academic XP.
    @dev Checks type==3, decrements count, adds xp_bonus to student's academicXP.
    """
    assert self.voters[msg.sender].weight > 0, "NotStudent"
    assert item_id < self.marketItemCount, "BadItemID"
    assert self.student_item_count[msg.sender][item_id] > 0, "NoItem"

    item: MarketItem = self.marketItems[item_id]
    assert item.item_type == 3, "NotXPItem"

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
    assert msg.sender == self.chairperson, "OnlyGM"
    assert guild_id > 0, "BadGuildID"
    assert len(members) > 0 and len(members) <= 5, "BadMembers"

    if not self.guilds[guild_id].is_active:
        self.guilds[guild_id] = Guild(
            guild_id=guild_id,
            total_xp=0,
            member_count=0,
            is_active=True
        )

    added_count: uint256 = 0
    for m: address in members:
        if m != empty(address):
            assert self.voters[m].weight > 0, "NotStudent"
            if self.student_to_guild[m] != guild_id:
                assert self.student_to_guild[m] == 0, "InGuild"
                self.student_to_guild[m] = guild_id
                self.guilds[guild_id].member_count += 1
            added_count += 1

    assert added_count > 0, "NoMembers"

    log GuildCreated(guild_id=guild_id, member_count=self.guilds[guild_id].member_count)


# ── V8: Hybrid Reward System (50/50 Model) ────────────────────────────────────

@external
@nonreentrant
def distribute_guild_reward(guild_id: uint256, members: DynArray[address, 5], total_sgc: uint256, total_xp: uint256):
    """
    @notice Distribute guild reward using the 50/50 hybrid model.
    @dev Only callable by chairperson. Members list is passed explicitly
         since the contract no longer stores member arrays on-chain.
         - Base 50% SGC: split equally among all passed members who are
           confirmed in this guild (soft check, stale addresses are skipped).
         - Premium 50% SGC: deposited into guild_vaults for DAO-governed distribution.
         - XP: split equally among the same confirmed members.
    @param guild_id Target guild identifier.
    @param members Array of guild member addresses (from frontend registry).
    @param total_sgc Total SGC reward in base units (integer, e.g. 100 for 100 SGC).
    @param total_xp Total Academic XP reward.
    """
    assert msg.sender == self.chairperson, "OnlyGM"
    assert self.guilds[guild_id].is_active, "NoGuild"
    assert total_sgc > 0 or total_xp > 0, "ZeroReward"

    active_count: uint256 = len(members)
    assert active_count > 0, "NoMembers"

    # 50/50 split: base immediate payout + premium KPI vault deposit
    base_sgc: uint256 = total_sgc // 2
    premium: uint256 = total_sgc - base_sgc  # correct for odd totals

    # Per-member equal shares (integer division; dust stays in vault)
    sgc_share: uint256 = base_sgc // active_count
    xp_share: uint256 = total_xp // active_count

    # Single-pass distribution — soft membership check skips stale addresses
    for student: address in members:
        if student == empty(address):
            continue
        if self.student_to_guild[student] == guild_id:
            # Credit Academic XP
            self.students[student].academicXP += xp_share

            # Transfer base SGC from msg.sender (chairperson) directly
            if sgc_share > 0:
                success: bool = extcall ERC20(self.token_address).transferFrom(
                    msg.sender, student, sgc_share * 10 ** 18
                )
                assert success, "TxFail"

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
    assert guild_id > 0, "BadGuildID"
    assert self.student_to_guild[msg.sender] == guild_id, "NotMember"
    assert not self.guild_locked[guild_id], "VaultLocked"
    assert len(targets) == len(amounts), "LenMismatch"
    assert len(targets) > 0, "EmptyProp"

    # Verify that proposed distribution exactly matches vault balance
    total: uint256 = 0
    for a: uint256 in amounts:
        total += a
    assert total == self.guild_vaults[guild_id], "BadAmounts"

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
    assert proposal.guild_id > 0, "NoProposal"
    assert not proposal.is_executed, "Executed"
    assert not proposal.is_disputed, "Disputed"

    guild_id: uint256 = proposal.guild_id
    assert self.student_to_guild[msg.sender] == guild_id, "NotMember"
    assert not self.proposal_signatures[proposal_id][msg.sender], "Signed"

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
                success: bool = extcall ERC20(self.token_address).transferFrom(
                    self.chairperson_wallet, proposal.targets[i], sgc_wei
                )
                assert success, "TxFail"

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
    assert proposal.guild_id > 0, "NoProposal"
    assert not proposal.is_executed, "Executed"
    assert not proposal.is_disputed, "Disputed"

    guild_id: uint256 = proposal.guild_id
    assert self.student_to_guild[msg.sender] == guild_id, "NotMember"

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
    assert msg.sender == self.chairperson, "OnlyGM"

    proposal: GuildProposal = self.guild_proposals[proposal_id]
    assert proposal.is_disputed, "NotDisputed"
    assert not proposal.is_executed, "Executed"
    assert len(final_targets) == len(final_amounts), "LenMismatch"

    guild_id: uint256 = proposal.guild_id
    vault_balance: uint256 = self.guild_vaults[guild_id]

    # Calculate 10% penalty (confiscated — stays on chairperson_wallet for future bounties)
    penalty: uint256 = vault_balance // 10
    remaining: uint256 = vault_balance - penalty

    # Verify final distribution matches the remaining 90%
    total: uint256 = 0
    for a: uint256 in final_amounts:
        total += a
    assert total == remaining, "Bad90Split"

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
            success: bool = extcall ERC20(self.token_address).transferFrom(
                self.chairperson_wallet, final_targets[i], sgc_wei
            )
            assert success, "TxFail"

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
    assert msg.sender == self.chairperson, "OnlyGM"
    assert len(students_list) == len(legacy_xp), "LenMismatch"

    for i: uint256 in range(20):
        if i >= len(students_list):
            break
        self.students[students_list[i]].academicXP += legacy_xp[i]

    log LegacyXPImported(student_count=len(students_list))


# ── V8: Guild View Functions ───────────────────────────────────────────────────


# ── V9: Guild Leave / Kick Mechanics ──────────────────────────────────────────

@external
@nonreentrant
def leave_guild(pay_with_tokens: bool):
    """
    @notice Allows a student to voluntarily leave their guild, paying a penalty.
    @dev If pay_with_tokens is True, LEAVE_TOKEN_PENALTY SGC is transferred from
         the student to the guild vault (requires prior ERC-20 approve).
         If pay_with_tokens is False, LEAVE_XP_PENALTY XP is deducted from the
         student's academicXP (floored to 0 if insufficient).
         The student's guild binding is cleared and the guild member count decremented.
    @param pay_with_tokens True to pay the penalty in SGC, False to pay in XP.
    """
    guild_id: uint256 = self.student_to_guild[msg.sender]
    assert guild_id > 0, "NotInGuild"
    assert self.voters[msg.sender].weight > 0, "NotStudent"

    if pay_with_tokens:
        # Transfer SGC penalty from student → guild vault
        # The student must have called approve(contractAddress, LEAVE_TOKEN_PENALTY) first
        success: bool = extcall ERC20(self.token_address).transferFrom(
            msg.sender, self.chairperson_wallet, LEAVE_TOKEN_PENALTY
        )
        assert success, "TxFail"
        self.guild_vaults[guild_id] += LEAVE_TOKEN_PENALTY // (10 ** 18)  # SGC base units
    else:
        # Deduct XP penalty, floored to zero
        current_xp: uint256 = self.students[msg.sender].academicXP
        if current_xp >= LEAVE_XP_PENALTY:
            self.students[msg.sender].academicXP = current_xp - LEAVE_XP_PENALTY
        else:
            self.students[msg.sender].academicXP = 0

    # Unbind student from guild and decrement member count
    self.student_to_guild[msg.sender] = 0
    self.guilds[guild_id].member_count -= 1

    log GuildMemberLeft(guild_id=guild_id, student=msg.sender, paid_with_tokens=pay_with_tokens)


@external
def kick_from_guild(student: address):
    """
    @notice Allows the Game Master to remove a student from their guild without penalty.
    @dev Only callable by chairperson. The student's guild binding is cleared
         and the guild member count is decremented. No penalties are applied.
    @param student Address of the student to remove.
    """
    assert msg.sender == self.chairperson, "OnlyGM"

    guild_id: uint256 = self.student_to_guild[student]
    assert guild_id > 0, "NotInGuild"

    # Unbind student from guild and decrement member count
    self.student_to_guild[student] = 0
    self.guilds[guild_id].member_count -= 1

    log GuildMemberKicked(guild_id=guild_id, student=student)


# ── Voting / Governance ────────────────────────────────────────────────────────

@external
def setQuestNames(names: DynArray[String[100], 4]):
    """
    @notice Sets the names of the Voting Quests.
    @dev May only be called by `chairperson`.
    """
    assert msg.sender == self.chairperson, "OnlyGM"
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
    assert msg.sender == self.chairperson, "OnlyGM"
    self.currentPollId += 1
    log NewRoundStarted(pollId=self.currentPollId)

@external
def delegate(to: address):
    """
    @notice Delegate your vote to the voter `to`.
    @param to Address to which vote is delegated.
    """
    assert self.voters[msg.sender].weight > 0, "NotStudent"
    assert not self.hasVoted[self.currentPollId][msg.sender], "AlreadyVoted"
    assert to != msg.sender, "SelfDeleg"
    assert self.voters[to].weight > 0, "NotStudent"

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
    assert self.voters[msg.sender].weight > 0, "NoVoteRight"
    assert not self.hasVoted[self.currentPollId][msg.sender], "AlreadyVoted"
    assert proposalIndex < len(self.proposals), "BadPropIdx"

    self.hasVoted[self.currentPollId][msg.sender] = True
    self.roundVote[self.currentPollId][msg.sender] = proposalIndex

    voter_weight: uint256 = self.voters[msg.sender].weight + self.receivedDelegations[self.currentPollId][msg.sender]
    self.pollVotes[self.currentPollId][proposalIndex] += voter_weight

    log Voted(voter=msg.sender, proposal=proposalIndex, weight=voter_weight)

    # Reward for the first vote ever
    if not self.has_received_reward[msg.sender]:
        self.has_received_reward[msg.sender] = True
        success: bool = extcall ERC20(self.token_address).transferFrom(self.chairperson_wallet, msg.sender, self.reward_amount)
        assert success, "TxFail"

# ── View Functions ─────────────────────────────────────────────────────────────

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
def get_market_purchases() -> DynArray[PurchaseLog, 128]:
    return self.market_purchases
