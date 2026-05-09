# pragma version 0.4.3

# ERC-20 Token: Stefany Gravity Coin (SGC)

event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256

event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256

name: public(String[32])
symbol: public(String[32])
decimals: public(uint8)
totalSupply: public(uint256)

balances: HashMap[address, uint256]
allowances: HashMap[address, HashMap[address, uint256]]

owner: public(address)

@deploy
def __init__():
    self.name = "Stefany Gravity Coin"
    self.symbol = "SGC"
    self.decimals = 18
    self.owner = msg.sender
    
    # 1,000,000 tokens
    initial_supply: uint256 = 1_000_000 * 10 ** 18
    self.totalSupply = initial_supply
    self.balances[msg.sender] = initial_supply
    
    log Transfer(sender=empty(address), receiver=msg.sender, value=initial_supply)

@external
@view
def balanceOf(_owner: address) -> uint256:
    return self.balances[_owner]

@external
@view
def allowance(_owner: address, _spender: address) -> uint256:
    return self.allowances[_owner][_spender]

@external
def transfer(_to: address, _value: uint256) -> bool:
    self.balances[msg.sender] -= _value
    self.balances[_to] += _value
    log Transfer(sender=msg.sender, receiver=_to, value=_value)
    return True

@external
def transferFrom(_from: address, _to: address, _value: uint256) -> bool:
    self.allowances[_from][msg.sender] -= _value
    self.balances[_from] -= _value
    self.balances[_to] += _value
    log Transfer(sender=_from, receiver=_to, value=_value)
    return True

@external
def approve(_spender: address, _value: uint256) -> bool:
    self.allowances[msg.sender][_spender] = _value
    log Approval(owner=msg.sender, spender=_spender, value=_value)
    return True

@external
def mint(_to: address, _value: uint256) -> bool:
    assert msg.sender == self.owner, "Only owner can mint"
    self.totalSupply += _value
    self.balances[_to] += _value
    log Transfer(sender=empty(address), receiver=_to, value=_value)
    return True
