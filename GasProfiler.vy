# pragma version ^0.4.0

interface Voter:
    def delegate(to: address): nonpayable
    def vote(proposalIndex: uint256): nonpayable
    def winning_proposal() -> uint256: view
    def _winning_proposal() -> uint256: view

@external
def measure_delegate(voter: address, target: address) -> uint256:
    start_gas: uint256 = msg.gas
    extcall Voter(voter).delegate(target)
    end_gas: uint256 = msg.gas
    return start_gas - end_gas

@external
def measure_vote(voter: address, proposal: uint256) -> uint256:
    start_gas: uint256 = msg.gas
    extcall Voter(voter).vote(proposal)
    end_gas: uint256 = msg.gas
    return start_gas - end_gas

@external
def measure_winning_proposal(voter: address) -> uint256:
    start_gas: uint256 = msg.gas
    res: uint256 = staticcall Voter(voter).winning_proposal()
    end_gas: uint256 = msg.gas
    return start_gas - end_gas
