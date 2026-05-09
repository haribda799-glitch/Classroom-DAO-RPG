import pytest
import boa

@pytest.fixture
def token():
    """
    Развертывает контракт и возвращает его объект.
    Деплоер автоматически становится владельцем (owner).
    """
    return boa.load("contracts/Token.vy")

@pytest.fixture
def owner(token):
    # Деплоер в titanoboa - это boa.env.eoa по умолчанию
    return boa.env.eoa

@pytest.fixture
def alice():
    return boa.env.generate_address("alice")

@pytest.fixture
def bob():
    return boa.env.generate_address("bob")

def test_initial_state(token, owner):
    """Проверка метаданных и начальной эмиссии."""
    assert token.name() == "Stefany Gravity Coin"
    assert token.symbol() == "SGC"
    assert token.decimals() == 18
    
    initial_supply = 1_000_000 * 10 ** 18
    assert token.totalSupply() == initial_supply
    assert token.balanceOf(owner) == initial_supply

def test_transfer_success(token, owner, alice):
    """Успешный перевод и проверка события Transfer."""
    transfer_amount = 100 * 10 ** 18
    initial_supply = 1_000_000 * 10 ** 18
    
    assert token.transfer(alice, transfer_amount, sender=owner)
    
    # Сразу получаем логи, иначе вызовы balanceOf перезапишут последнюю транзакцию
    logs = token.get_logs()
    
    assert token.balanceOf(owner) == initial_supply - transfer_amount
    assert token.balanceOf(alice) == transfer_amount
    
    # Проверка логов (событий)
    transfer_logs = [log for log in logs if type(log).__name__ == "Transfer"]
    
    # Ожидаем 1 событие от вызванного transfer
    assert len(transfer_logs) == 1
    
    last_log = transfer_logs[0]
    assert last_log.receiver == alice
    assert last_log.value == transfer_amount

def test_transfer_insufficient_balance(token, owner, alice):
    """Ошибка при недостаточном балансе."""
    # У Алисы изначальный баланс 0, она пытается перевести токены
    with boa.reverts():
        token.transfer(owner, 10, sender=alice)

def test_approve_and_transfer_from(token, owner, alice, bob):
    """Механика approve и transferFrom с проверкой уменьшения лимита."""
    allowance_amount = 50 * 10 ** 18
    
    # Владелец разрешает Алисе потратить 50 SGC
    assert token.approve(alice, allowance_amount, sender=owner)
    assert token.allowance(owner, alice) == allowance_amount
    
    # Алиса переводит 50 SGC от Владельца к Бобу
    assert token.transferFrom(owner, bob, allowance_amount, sender=alice)
    
    # Проверяем, что токены дошли до Боба
    assert token.balanceOf(bob) == allowance_amount
    
    # Проверяем, что allowance уменьшился до 0
    assert token.allowance(owner, alice) == 0

def test_transfer_from_insufficient_allowance(token, owner, alice, bob):
    """Ошибка при попытке перевести больше, чем позволено в allowance."""
    allowance_amount = 50 * 10 ** 18
    token.approve(alice, allowance_amount, sender=owner)
    
    with boa.reverts():
        token.transferFrom(owner, bob, allowance_amount + 1, sender=alice)

def test_mint_success(token, owner, alice):
    """Успешная дополнительная эмиссия от владельца."""
    mint_amount = 50_000 * 10 ** 18
    initial_supply = token.totalSupply()
    
    assert token.mint(alice, mint_amount, sender=owner)
    
    assert token.totalSupply() == initial_supply + mint_amount
    assert token.balanceOf(alice) == mint_amount

def test_mint_failure(token, alice, bob):
    """Ошибка эмиссии от любого другого адреса (не owner)."""
    with boa.reverts("Only owner can mint"):
        token.mint(bob, 100, sender=alice)
